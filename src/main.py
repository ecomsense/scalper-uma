# Main Controller App - APScheduler, PID lock, HTTP auth, page routing
from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import signal
import sys
from base64 import b64decode
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from traceback import print_exc
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pytz import timezone as tz
from sse_starlette.sse import EventSourceResponse

from src.constants import (
    O_CNFG,
    O_FUTL,
    O_SETG,
    S_DATA,
    TRADE_JSON,
    dct_sym,
    logging,
)
from src.state import _logic_state, get_logic_state

from src.logic_app import (
    create_logic_router,
    get_settings,
    get_status,
    load_template,
    pause_logic,
    start_logic,
    stop_logic,
    trading_session_start,
    trading_session_stop,
)


# ============================================================
# Constants
# ============================================================

IST = tz('Asia/Kolkata')
SCHEDULER = AsyncIOScheduler()
STATIC_DIR = Path(__file__).parent / 'static'
CANDLESTICK_TIMEFRAME_SECONDS = 60


# ============================================================
# PID Lock File
# ============================================================

LOCK_FILE = Path(__file__).parent.parent / 'data' / 'app.pid'


def check_pid_lock() -> bool:
    if not LOCK_FILE.exists():
        return True
    try:
        old_pid = int(LOCK_FILE.read_text().strip())
        os.kill(old_pid, 0)
        logging.error(f'Another instance is running (PID: {old_pid}). Exiting.')
        return False
    except OSError:
        logging.info(f'Stale lock file found (PID: {old_pid}). Proceeding.')
        return True


def acquire_pid_lock() -> None:
    LOCK_FILE.write_text(str(os.getpid()))
    logging.info(f'PID lock acquired: {os.getpid()}')


def release_pid_lock() -> None:
    if LOCK_FILE.exists():
        try:
            current_pid = int(LOCK_FILE.read_text().strip())
            if current_pid == os.getpid():
                LOCK_FILE.unlink()
                logging.info('PID lock released')
        except (ValueError, IOError):
            pass


_is_lock_enabled = os.environ.get('SKIP_PID_LOCK', '') != '1'


# ============================================================
# HTTP Basic Auth
# ============================================================

def get_auth_credentials() -> tuple[str, str] | None:
    auth = os.environ.get('HTTP_AUTH', '')
    if not auth:
        return None
    try:
        username, password = auth.split(':', 1)
        return (username, password)
    except ValueError:
        return None


def verify_basic_auth(request: Request) -> bool:
    credentials = get_auth_credentials()
    if credentials is None:
        return True
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Basic '):
        return False
    try:
        encoded = auth_header[6:]
        decoded = b64decode(encoded).decode('utf-8')
        provided_user, provided_pass = decoded.split(':', 1)
        return provided_user == credentials[0] and provided_pass == credentials[1]
    except Exception:
        return False


# ============================================================
# Schedule Configuration
# ============================================================

class ScheduleConfig:
    def __init__(self):
        self.enabled = True
        self.start_hour = 2
        self.start_minute = 0
        self.end_hour = 15
        self.end_minute = 31
        self.trading_days = [0, 1, 2, 3, 4]
        self.trading_day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

    def is_within_schedule(self) -> bool:
        if not self.enabled:
            return True
        if _logic_state.is_paused():
            return False
        now = datetime.now()
        if now.weekday() not in self.trading_days:
            return False
        current_minutes = now.hour * 60 + now.minute
        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute
        return start_minutes <= current_minutes < end_minutes

    def is_paused(self) -> bool:
        return _logic_state.is_paused()

    def pause_reason(self) -> str:
        if _logic_state.paused and _logic_state.pause_until:
            remaining = (_logic_state.pause_until - datetime.now()).total_seconds()
            if remaining > 0:
                return f'{_logic_state.pause_reason} ({int(remaining)}s)'
        return ''

    def can_start(self) -> bool:
        return self.is_within_schedule() and not _logic_state.is_running()

    def time_until_start(self) -> str:
        if not self.enabled or self.is_within_schedule():
            return 'now'
        now = datetime.now()
        start_minutes = self.start_hour * 60 + self.start_minute
        current_minutes = now.hour * 60 + now.minute
        mins_until = start_minutes - current_minutes
        if mins_until < 0:
            mins_until += 1440
        hours = mins_until // 60
        mins = mins_until % 60
        if hours > 0:
            return f'{hours}h {mins}m'
        return f'{mins}m'

    def time_until_end(self) -> str:
        if not self.enabled or not self.is_within_schedule():
            return 'outside'
        now = datetime.now()
        end_minutes = self.end_hour * 60 + self.end_minute
        current_minutes = now.hour * 60 + now.minute
        mins_until = end_minutes - current_minutes
        if mins_until <= 0:
            return 'now'
        hours = mins_until // 60
        mins = mins_until % 60
        if hours > 0:
            return f'{hours}h {mins}m'
        return f'{mins}m'


schedule_config = ScheduleConfig()


# ============================================================
# Scheduler Jobs
# ============================================================

async def scheduled_start():
    if schedule_config.can_start():
        await start_logic()


async def scheduled_stop():
    if _logic_state.is_running() and not schedule_config.is_within_schedule():
        await stop_logic()


async def watchdog_check():
    if schedule_config.is_within_schedule() and not _logic_state.is_running():
        await start_logic()
    elif not schedule_config.is_within_schedule() and _logic_state.is_running():
        await stop_logic()


# ============================================================
# Memory Tracking
# ============================================================

def get_memory_usage() -> dict:
    gc.collect()
    return {
        'logic_state_bytes': sys.getsizeof(_logic_state),
        'startup_data_bytes': sys.getsizeof(_logic_state.startup_data) if _logic_state.startup_data else 0,
        'app_data_bytes': sys.getsizeof(_logic_state.app_data) if _logic_state.app_data else 0,
        'ws_bytes': sys.getsizeof(_logic_state.ws) if _logic_state.ws else 0,
    }


# ============================================================
# Page Template Loader
# ============================================================

def load_page_template(name: str) -> str:
    template_path = Path(__file__).parent.parent / 'templates' / f'{name}.html'
    return template_path.read_text()


# ============================================================
# FastAPI App Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logic = _logic_state
    
    if _is_lock_enabled:
        if not check_pid_lock():
            logging.error('Another instance is running. Exiting.')
            sys.exit(1)
        acquire_pid_lock()
    
    if schedule_config.enabled:
        SCHEDULER.add_job(watchdog_check, trigger=IntervalTrigger(seconds=60), id='watchdog_check')
        SCHEDULER.start()
    
    yield
    
    if SCHEDULER.running:
        SCHEDULER.shutdown()
    release_pid_lock()


app = FastAPI(
    title='UMA Scalper Controller',
    description='Control trading with schedule',
    version='1.0.0',
    lifespan=lifespan,
)


# ============================================================
# HTTP Auth Middleware
# ============================================================

@app.middleware('http')
async def auth_middleware(request: Request, call_next):
    if not verify_basic_auth(request):
        return JSONResponse(
            content={'detail': 'Unauthorized'},
            status_code=401,
            headers={'WWW-Authenticate': 'Basic realm=Restricted'}
        )
    return await call_next(request)


app.mount('/static', StaticFiles(directory=STATIC_DIR, html=True), name='static')


# ============================================================
# Routes - Page Routing
# ============================================================

@app.get('/', response_class=HTMLResponse)
async def root():
    if schedule_config.is_within_schedule() and _logic_state.is_running():
        return HTMLResponse(load_page_template('logic'))
    return HTMLResponse(load_page_template('sleeping'))


@app.get('/logic', response_class=HTMLResponse)
async def logic_page():
    if schedule_config.is_within_schedule() and _logic_state.is_running():
        return HTMLResponse(load_page_template('logic'))
    return HTMLResponse(load_page_template('sleeping'))
        return HTMLResponse(load_page_template('logic'))
    return HTMLResponse(load_page_template('sleeping'))


# ============================================================
# Routes - Schedule & Status
# ============================================================

@app.get('/api/schedule')
async def schedule_info():
    return {
        'enabled': schedule_config.enabled,
        'start_time': f'{schedule_config.start_hour:02d}:{schedule_config.start_minute:02d}',
        'end_time': f'{schedule_config.end_hour:02d}:{schedule_config.end_minute:02d}',
        'within_schedule': schedule_config.is_within_schedule(),
        'time_until_start': schedule_config.time_until_start(),
        'time_until_end': schedule_config.time_until_end(),
        'running': _logic_state.is_running(),
        'paused': schedule_config.is_paused(),
        'pause_reason': schedule_config.pause_reason(),
        'schedule_times': f'{schedule_config.start_hour:02d}:{schedule_config.start_minute:02d} - {schedule_config.end_hour:02d}:{schedule_config.end_minute:02d}',
        'trading_days': schedule_config.trading_day_names,
    }


@app.get('/api/memory')
async def memory_info():
    return {
        'running': _logic_state.is_running(),
        'has_startup_data': _logic_state.startup_data is not None,
        'has_app_data': _logic_state.app_data is not None,
        'has_ws': _logic_state.ws is not None,
        'schedule_enabled': schedule_config.enabled,
        'within_schedule': schedule_config.is_within_schedule(),
        'time_until_end': schedule_config.time_until_end(),
        **get_memory_usage(),
    }


# ============================================================
# Routes - Admin
# ============================================================

@app.get('/api/admin/logs')
async def get_logs():
    try:
        log_path = Path(S_DATA) / 'log.txt'
        if log_path.exists():
            content = log_path.read_text()[-5000:]
        else:
            content = 'No logs found'
        return JSONResponse(content={'content': content, 'status': 'ok'})
    except Exception as e:
        return JSONResponse(content={'content': f'Error: {e}', 'status': 'error'}, status_code=500)


@app.get('/api/admin/settings')
async def get_settings_file():
    try:
        settings_path = Path(S_DATA) / 'settings.yml'
        with open(settings_path) as f:
            content = f.read()
        return JSONResponse(content={'content': content, 'status': 'success'})
    except Exception as e:
        return JSONResponse(content={'message': str(e), 'status': 'error'}, status_code=500)


@app.post('/api/admin/settings')
async def update_settings(request: Request, settings_data: dict[str, Any] = Body(...)):
    try:
        settings_path = Path(S_DATA) / 'settings.yml'
        content = settings_data.get('content', '')
        with open(settings_path, 'w') as f:
            f.write(content)
        await stop_logic()
        return JSONResponse(content={'message': 'Settings saved. Trading stopped.', 'status': 'success'})
    except Exception as e:
        return JSONResponse(content={'message': str(e), 'status': 'error'}, status_code=500)


@app.get('/api/admin/status')
async def get_admin_status():
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    return JSONResponse(content={
        'status': 'running',
        'current_time_ist': now_ist.strftime('%H:%M'),
        'day_of_week': now_ist.strftime('%a'),
        'is_trading': _logic_state.is_running(),
        'within_schedule': schedule_config.is_within_schedule(),
    })


@app.get('/api/chart/settings')
async def get_chart_settings():
    try:
        ma = O_SETG.get('ma', [])
        base = O_SETG.get('base', 'NIFTY')
        base_settings = O_SETG.get(base, {})
        profit = base_settings.get('profit', 5) if isinstance(base_settings, dict) else 5
        return JSONResponse(content={'ma': ma, 'profit': profit})
    except Exception as e:
        return JSONResponse(content={'error': str(e)}, status_code=500)


# ============================================================
# Routes - Trading (Live Trading)
# ============================================================

@app.get('/api/symbols')
async def get_available_symbols(request: Request) -> JSONResponse:
    symbols = list(_logic_state.tokens_nearest.values())
    return JSONResponse(content=symbols)


@app.get('/api/summary')
async def get_summary(request: Request) -> JSONResponse:
    try:
        from src.api import Helper
        content = Helper.summary()
        if not content:
            return JSONResponse(content={'error': 'api not initialized'}, status_code=500)
        return JSONResponse(content)
    except Exception as e:
        logging.error(f'Error getting summary: {e}')
        return JSONResponse(content={'error': str(e)}, status_code=500)


@app.get('/api/orders')
async def get_orders(request: Request) -> JSONResponse:
    try:
        from src.api import Helper
        orders = Helper.orders()
        logging.info(f'Orders count: {len(orders) if orders else 0}')
        return JSONResponse(content={'orders': orders})
    except Exception as e:
        logging.error(f'Error getting orders: {e}')
        return JSONResponse(content={'orders': []})


@app.get('/api/historical/{symbol}')
async def get_historical_data(symbol: str, request: Request) -> JSONResponse:
    try:
        tokens_nearest = _logic_state.tokens_nearest
        ws_token = next((k for k, v in tokens_nearest.items() if v == symbol), None)
        if not ws_token:
            return JSONResponse(content={'error': 'Symbol not found'}, status_code=404)

        parts = ws_token.split('|')
        exchange, token = parts[0], parts[1]

        from src.api import Helper
        historical_data = Helper.historical(exchange, token)

        if not historical_data or len(historical_data) == 0:
            return JSONResponse(content={'data': []})

        candlesticks = []
        for row in historical_data:
            candlesticks.append({
                'time': int(row.get('ssboe', row.get('ut', 0))),
                'open': float(row.get('into', row.get('open', 0))),
                'high': float(row.get('inth', row.get('high', 0))),
                'low': float(row.get('intl', row.get('low', 0))),
                'close': float(row.get('intc', row.get('close', 0))),
            })

        return JSONResponse(content={'data': candlesticks})
    except Exception as e:
        logging.error(f'Error in historical: {e}')
        return JSONResponse(content={'error': str(e)}, status_code=500)


@app.post('/api/trade/buy')
async def place_buy_order(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    logging.debug(f'Order request received: {payload}')

    symbol = payload.get('symbol', 'DUMMY').upper()
    if symbol != 'DUMMY':
        settings = get_settings()

        order_details = {
            'symbol': symbol,
            'quantity': _logic_state.quantity,
            'disclosed_quantity': 0,
            'exchange': settings.get('option_exchange', 'NFO'),
            'tag': payload.pop('tag', 'no_tag'),
            'side': 'BUY',
        }

        exit_price = payload.pop('exit_price')
        cost_price = payload.pop('cost_price')
        order_details.update(payload)

        from src.api import Helper
        order_id = Helper.one_side(order_details)
        if order_id:
            order_details['entry_id'] = order_id
            order_details['exit_price'] = exit_price
            order_details['target_price'] = cost_price + settings.get('profit', 5)
            if order_details['tag'] != 'no_tag':
                order_details['target_price'] = cost_price + (cost_price - exit_price)

            order_type = order_details.get('order_type', 'LIMIT')
            if order_type == 'SL':
                Helper.cancel_orders(symbol, keep_order_id=order_id)
            else:
                Helper.cancel_orders(symbol, keep_order_id=order_id, side='BUY')

            blacklist = ['side', 'price', 'trigger_price', 'order_type']
            for key in blacklist:
                order_details.pop(key, None)
            O_FUTL.write_file(filepath=TRADE_JSON, content=order_details)
            return JSONResponse(content={'message': f'Buy order initiated for {symbol}', 'status': 'success', 'order': order_details})

        return JSONResponse(content={'message': 'error while buy order', 'status': 'failed', 'order': order_details})


@app.get('/api/trade/sell')
async def reset(symbol: str = '', ltp: float = 0) -> JSONResponse:
    try:
        from src.api import Helper
        logging.debug(f'Cancel requested: symbol={symbol}, ltp={ltp}')
        Helper.close_all_for_symbol(symbol, ltp)
        return JSONResponse(content={'message': 'reset completed', 'status': 'success'})
    except Exception as e:
        logging.error(f'Cancel error: {e}')
        return JSONResponse(content={'message': str(e), 'status': 'error'}, status_code=500)


# ============================================================
# Routes - SSE Streaming
# ============================================================

@app.get('/sse/candlesticks/{symbol}')
async def sse_candlestick_endpoint(symbol: str, request: Request) -> EventSourceResponse:
    logging.debug(f'SSE connection requested for symbol: {symbol}')

    last_sent_candle: dict[str, Any] | None = None

    async def event_generator():
        nonlocal last_sent_candle
        ws = _logic_state.ws
        token_symbols = _logic_state.tokens_nearest

        try:
            token_symbol = next(k for k, v in token_symbols.items() if v == symbol)
        except (KeyError, IndexError):
            return

        waited = 0
        while token_symbol not in ws.ltp and waited < 60:
            await asyncio.sleep(0.5)
            waited += 1

        if token_symbol not in ws.ltp:
            return

        while True:
            await asyncio.sleep(0.5)

            try:
                price = ws.ltp.get(token_symbol)
                if price is None:
                    continue

                ist_now = datetime.now(IST)
                current_timestamp_ist = int(ist_now.timestamp())
                candle_time = current_timestamp_ist - (current_timestamp_ist % CANDLESTICK_TIMEFRAME_SECONDS)

                if last_sent_candle is None or candle_time > last_sent_candle['time']:
                    if last_sent_candle is not None:
                        yield {'event': 'live_update', 'data': json.dumps(last_sent_candle)}

                    last_sent_candle = {
                        'open': price, 'high': price, 'low': price,
                        'close': price, 'volume': 0, 'time': candle_time,
                    }
                else:
                    last_sent_candle['high'] = max(last_sent_candle['high'], price)
                    last_sent_candle['low'] = min(last_sent_candle['low'], price)
                    last_sent_candle['close'] = price

                yield {'event': 'live_update', 'data': json.dumps(last_sent_candle)}

            except Exception:
                continue

    return EventSourceResponse(event_generator())


@app.get('/sse/orders')
async def stream_all_orders(request: Request) -> EventSourceResponse:
    async def event_generator():
        while True:
            ws = _logic_state.ws
            if ws and ws.order_updates:
                order_msg = ws.order_updates.popleft()
                msg_str = json.dumps(order_msg)
                logging.debug(f'SSE sending order_msg: {order_msg}')
                yield {'event': 'order_msg', 'data': msg_str}
            else:
                await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())


# ============================================================
# Routes - Logic App (Mounted)
# ============================================================

logic_router = create_logic_router()
app.include_router(logic_router, prefix='/api/logic')


# ============================================================
# Debug Routes (for development)
# ============================================================

@app.post('/api/admin/restart')
async def restart_trading_session(request: Request) -> JSONResponse:
    try:
        await stop_logic()
        await start_logic()
        return JSONResponse(content={'message': 'Trading session restarted', 'status': 'success'})
    except Exception as e:
        return JSONResponse(content={'message': f'Failed to restart: {e}', 'status': 'error'}, status_code=500)


@app.post('/api/admin/start')
async def admin_start_session(request: Request) -> JSONResponse:
    try:
        await start_logic()
        return JSONResponse(content={'message': 'Trading session started', 'status': 'success'})
    except Exception as e:
        return JSONResponse(content={'message': f'Failed to start: {e}', 'status': 'error'}, status_code=500)


@app.post('/api/admin/stop')
async def admin_stop_session(request: Request) -> JSONResponse:
    try:
        await stop_logic()
        return JSONResponse(content={'message': 'Trading session stopped', 'status': 'success'})
    except Exception as e:
        return JSONResponse(content={'message': f'Failed to stop: {e}', 'status': 'error'}, status_code=500)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)