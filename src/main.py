# main.py
from __future__ import annotations
from src.api import Helper
from src.constants import (
    access_setg,
    access_cnfg,
    logging,
    O_FUTL,
    TRADE_JSON,
    S_DATA,
    HTPASSWD_FILE,
    dct_sym,
)
from functools import lru_cache
import pandas as pd
from fastapi import FastAPI, Body, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import json
from src.tickrunner import TickRunner
from src.wserver import Wserver
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sse_starlette.sse import EventSourceResponse
from src.strategy import Strategy
from src.constants import dct_sym
from traceback import print_exc

MARKER_FILE = Path(S_DATA) / "settings.marker"
SCHEDULER = AsyncIOScheduler()
from contextlib import asynccontextmanager

from pytz import timezone as tz
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Any, Optional


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != JWT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


IST = tz("Asia/Kolkata")


def touch_marker():
    """Touch the marker file to signal settings changed."""
    MARKER_FILE.touch()


def get_marker_mtime() -> float:
    """Get marker file modification time."""
    if MARKER_FILE.exists():
        return MARKER_FILE.stat().st_mtime
    return 0


def get_settings_timestamp() -> float:
    """Get settings file modification time."""
    settings_path = Path(S_DATA) / "settings.yml"
    if settings_path.exists():
        return settings_path.stat().st_mtime
    return 0


async def trading_session_start(app: FastAPI):
    """Start the trading session (called by scheduler or on settings change)."""
    logging.info("Starting trading session...")

    # Clear trade.json on session start - manually managed trades
    O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})

    # Cancel existing runner if any
    if hasattr(app.state, "runner_task"):
        app.state.runner_task.cancel()
        try:
            await app.state.runner_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # Get fresh settings
    user_settings = get_settings()

    try:
        api = Helper.api()

        # Get ATM from index LTP using websocket
        index_token = f"{user_settings['exchange']}|{user_settings['token']}"
        ws = Wserver(api, [index_token])

        # Wait for websocket to get LTP (max 30 seconds)
        max_wait = 60
        waited = 0
        while not ws.ltp and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 1

        if not ws.ltp:
            logging.error("Failed to get LTP from websocket")
            return

        ltp_of_underlying = list(ws.ltp.values())[0]
        logging.info(f"Got LTP for {user_settings['symbol']}: {ltp_of_underlying}")

        # Now create strategy and subscribe to options
        sgy = Strategy(user_settings, ltp_of_underlying)
        tokens = list(sgy.tokens_for_all_trading_symbols.keys())

        if not tokens:
            logging.warning("No tokens found for options")
            return

        # Subscribe to options on existing websocket
        all_tokens = tokens + [index_token]
        ws.subscribe(all_tokens)

        # Wait for options LTP
        waited = 0
        while len(ws.ltp) < len(all_tokens) and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 1

        logging.info(f"Got quotes for {len(ws.ltp)} symbols")

        symbol_nearest_to_premium: List[str] = []
        for ce_or_pe in ["CE", "PE"]:
            res = sgy.find_trading_symbol_by_atm(ce_or_pe, ws.ltp)
            if res:
                symbol_nearest_to_premium.append(res)

        tokens_nearest: Dict[str, str] = sgy.sym.find_wstoken_from_tradingsymbol(
            symbol_nearest_to_premium
        )

        app.state.tokens_nearest = tokens_nearest
        app.state.ws = ws
        app.state.quantity = user_settings["lots"] * sgy.sym.get_lot_size()
        logging.debug(
            f"quantity set: {user_settings['lots']} lots * {sgy.sym.get_lot_size()} lot_size = {app.state.quantity}"
        )

        all_tokens_map = sgy.tokens_for_all_trading_symbols
        logging.info(f"Passing {len(all_tokens_map)} tokens to TickRunner")
        runner = TickRunner(ws, all_tokens_map)
        task = asyncio.create_task(runner.run())
        app.state.runner_task = task
        app.state.is_trading = True

        logging.info(f"Nearest symbols: {tokens_nearest}")
        logging.info("✅ Trading session started.")

    except Exception as e:
        logging.error(f"Failed to start trading session: {e}")
        print_exc()


async def trading_session_stop(app: FastAPI):
    """Stop the trading session (called by scheduler or on settings change)."""
    logging.info("Stopping trading session...")

    if hasattr(app.state, "runner_task") and app.state.runner_task:
        app.state.runner_task.cancel()
        try:
            await app.state.runner_task
        except asyncio.CancelledError:
            logging.info("TickRunner task cancelled.")
        except Exception:
            pass
        app.state.runner_task = None

    logging.info("✅ Trading session stopped.")


def schedule_trading_session(app: FastAPI):
    """Schedule trading session start/stop based on settings file."""
    # Read times from settings
    settings = get_settings()
    program = settings.get("program", {})
    start_time = program.get("start", "09:14")
    stop_time = program.get("stop", "23:59")

    # Parse times
    start_parts = start_time.split(":")
    stop_parts = stop_time.split(":")

    start_hour = int(start_parts[0])
    start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
    stop_hour = int(stop_parts[0])
    stop_minute = int(stop_parts[1]) if len(stop_parts) > 1 else 0

    # Clear existing jobs if any
    for job_id in ["start_session", "stop_session"]:
        try:
            SCHEDULER.remove_job(job_id)
        except Exception:
            pass

    SCHEDULER.add_job(
        trading_session_start,
        trigger=CronTrigger(
            day_of_week="mon-fri", hour=start_hour, minute=start_minute
        ),
        id="start_session",
        args=[app],
    )

    SCHEDULER.add_job(
        trading_session_stop,
        trigger=CronTrigger(day_of_week="mon-fri", hour=stop_hour, minute=stop_minute),
        id="stop_session",
        args=[app],
    )

    logging.info(
        f"Trading session scheduled: {start_time}-{stop_time} Mon-Fri IST (from settings)"
    )


CANDLESTICK_TIMEFRAME_SECONDS: int = 60
CANDLESTICK_TIMEFRAME_STR: str = "1min"

IST_OFFSET: timedelta = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET)


# --- Helper Functions for Candlestick Aggregation ---
def aggregate_ticks_to_candlesticks(
    df: pd.DataFrame, timeframe_str: str = CANDLESTICK_TIMEFRAME_STR
) -> List[Dict[str, Any]]:
    try:
        if df.empty:
            return []

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        ohlc = df["price"].resample(timeframe_str).ohlc()
        volume = df["volume"].resample(timeframe_str).sum()

        candlesticks = pd.DataFrame(
            {
                "open": ohlc["open"],
                "high": ohlc["high"],
                "low": ohlc["low"],
                "close": ohlc["close"],
                "volume": volume,
            }
        )
        candlesticks = candlesticks.dropna()
        candlesticks["time"] = candlesticks.index.astype("int64") // 10**9

        return candlesticks.reset_index(drop=True).to_dict(orient="records")
    except Exception as e:
        logging.error(f"{e} in aggregating")
        return []


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    base = O_SETG["base"]
    settings = O_SETG[base] | dct_sym[base]
    return settings


# --- Application Lifespan Event ---
# Server runs 24/7, no scheduler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check schedule and start/stop accordingly
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    minute = now_ist.minute
    day = now_ist.strftime("%a")
    
    # Schedule: 9:15 to 23:59
    in_hours = (hour > 9 or (hour == 9 and minute >= 15)) and hour < 23 or (hour == 23 and minute < 59)
    is_trading_day = day in ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    if in_hours and is_trading_day:
        logging.info(f"Within schedule ({now_ist.strftime('%H:%M')}), starting trading session...")
        await trading_session_start(app)
    else:
        logging.info(f"Outside schedule ({now_ist.strftime('%H:%M')}), skipping trading session...")
    
    logging.info("✅ Trading session started.")

    yield

    # Shutdown: stop trading session
    await trading_session_stop(app)
    logging.info("✅ Trading session stopped.")


# --- FastAPI App Initialization ---
# Pass the lifespan function to the FastAPI constructor
app = FastAPI(lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/", include_in_schema=False)
async def serve_root(request: Request):
    is_trading = getattr(request.app.state, "is_trading", False)
    if not is_trading:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>UMA Scalper</title>
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body>
            <div class="container">
                <div class="app-header">
                    <h1>UMA Scalper</h1>
                    <div class="header-buttons">
                        <button class="blue-btn" onclick="document.getElementById('logsModal').style.display='block'">Logs</button>
                        <button class="blue-btn" onclick="document.getElementById('settingsModal').style.display='block'">Settings</button>
                    </div>
                </div>
                <div class="chart-grid">
                    <div class="chart-container" style="display:flex;align-items:center;justify-content:center;min-height:60vh;">
                        <div style="text-align:center;font-size:1.5em;">
                            <div style="font-size:3em;margin-bottom:10px;" id="sleepEmoji">&#128564;</div>
                            <h2 id="sleepMsg" style="color:#ffd700;">Zzz... sleeping</h2>
                            <p style="font-size:1.2em;margin:20px 0;" id="clock"></p>
                            <p style="font-size:1.1em;margin:15px 0;color:#888;">Trading hours: 09:14 - 23:59 IST</p>
                            <p style="font-size:1.1em;margin:15px 0;color:#888;">Trading days: Mon, Tue, Wed, Thu, Fri</p>
                        </div>
                    </div>
                </div>
                <div class="footer">
                    <span style="color:var(--text-primary);">made with </span><span style="color:red;">&#10084;</span><span style="color:var(--text-primary);"> by </span><a href="https://ecomsense.in" target="_blank" style="color:var(--accent-color);text-decoration:none;">ecomsense.in</a>
                </div>
            </div>
            <!-- Logs Modal -->
            <div id="logsModal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Server Logs</h2>
                        <span class="close" onclick="document.getElementById('logsModal').style.display='none'">&times;</span>
                    </div>
                    <textarea id="logsEditor" readonly style="width:100%;height:300px;background:#1a1a2e;color:#fff;"></textarea>
                    <div style="margin-top:10px;">
                        <button class="blue-btn" onclick="fetch('/api/admin/logs').then(r=>r.text()).then(t=>document.getElementById('logsEditor').value=t)">Refresh</button>
                    </div>
                </div>
            </div>
            <!-- Settings Modal -->
            <div id="settingsModal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Settings</h2>
                        <span class="close" onclick="document.getElementById('settingsModal').style.display='none'">&times;</span>
                    </div>
                    <textarea id="settingsEditor" style="width:100%;height:300px;background:#1a1a2e;color:#fff;"></textarea>
                    <div id="settingsMsg" style="margin-top:10px;color:#888;">Note: Trading is paused - settings will apply on next wake</div>
                </div>
            </div>
            <script>
              fetch('/api/admin/settings').then(r=>r.json()).then(d=>{if(d.status==='success')document.getElementById('settingsEditor').value=d.content;}).catch(e=>{});
            </script>
              const emojis = ["&#128564;", "&#127861;", "&#920043;", "&#127969;", "&#128166;", "&#128170;", "&#127804;"];
              const msgs = ["Zzz... sleeping", "Coffee break!", "Market siesta", "Hold your horses!", "Patience young padwan!", "Dreaming of profits...", "Counting sheep...", "Market meditation...", "Waiting for green candles..."];
              const el = document.getElementById('sleepEmoji');
              if(el) el.innerHTML = emojis[Math.floor(Math.random() * emojis.length)];
              const ml = document.getElementById('sleepMsg');
              if(ml) { ml.innerText = msgs[Math.floor(Math.random() * msgs.length)]; ml.style.color = ['#ffd700','#ff6b6b','#4ecdc4','#a855f7','#f97316'][Math.floor(Math.random()*5)]; }
              function updateClock() {
                const now = new Date();
                const ist = new Date(now.toLocaleString('en-US', {timeZone: 'Asia/Kolkata'}));
                const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
                document.getElementById('clock').innerText = days[ist.getDay()] + ', ' + ist.toLocaleTimeString('en-US', {timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}) + ' IST';
              }
              updateClock();
              setInterval(updateClock, 1000);
            </script>
        </body>
        </html>
        """)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/symbols")
async def get_available_symbols(request: Request) -> JSONResponse:
    """
    Returns a list of available symbols.
    """
    symbols = list(request.app.state.tokens_nearest.values())
    return JSONResponse(content=symbols)


@app.get("/api/summary")
async def get_summary(request: Request) -> JSONResponse:
    """
    Returns both positions and orders summary.
    """
    try:
        api = Helper.api()
        if not api:
            return JSONResponse(content={"error": "api not initialized"}, status_code=500)
        
        content = Helper.summary()
        return JSONResponse(content)
    except Exception as e:
        logging.error(f"Error getting summary: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/orders")
async def get_orders(request: Request) -> JSONResponse:
    """
    Returns all orders.
    """
    try:
        orders = Helper.orders()
        logging.info(f"Orders count: {len(orders) if orders else 0}")
        return JSONResponse(content={"orders": orders})
    except Exception as e:
        logging.error(f"Error getting orders: {e}")
        return JSONResponse(content={"orders": []})


@app.get("/api/historical/{symbol}")
async def get_historical_data(symbol: str, request: Request) -> JSONResponse:
    """
    Returns historical candlestick data for a symbol.
    """
    try:
        tokens_nearest = request.app.state.tokens_nearest
        logging.info(f"historical: symbol={symbol}, tokens_nearest={tokens_nearest}")

        ws_token = next((k for k, v in tokens_nearest.items() if v == symbol), None)
        if not ws_token:
            logging.warning(f"historical: ws_token not found for {symbol}")
            return JSONResponse(content={"error": "Symbol not found"}, status_code=404)

        parts = ws_token.split("|")
        exchange, token = parts[0], parts[1]
        logging.info(
            f"historical: before Helper.historical: Helper._api={Helper._api}, Helper._api.broker={Helper._api.broker}"
        )
        logging.info(f"historical: calling broker: exchange={exchange}, token={token}")

        historical_data = Helper.historical(exchange, token)
        logging.info(
            f"historical: got {len(historical_data) if historical_data else 0} rows"
        )

        if not historical_data or len(historical_data) == 0:
            return JSONResponse(content={"data": []})

        candlesticks = []
        for row in historical_data:
            candlesticks.append(
                {
                    "time": int(row["ssboe"]) if "ssboe" in row else int(row["ut"]),
                    "open": float(row["into"]) if "into" in row else float(row["open"]),
                    "high": float(row["inth"]) if "inth" in row else float(row["high"]),
                    "low": float(row["intl"]) if "intl" in row else float(row["low"]),
                    "close": (
                        float(row["intc"]) if "intc" in row else float(row["close"])
                    ),
                }
            )

        return JSONResponse(content={"data": candlesticks})
    except Exception as e:
        logging.error(f"Error in historical: {e}")
        print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/trade/buy")
async def place_buy_order(
    request: Request, payload: Dict[str, Any] = Body(...)
) -> JSONResponse:
    logging.debug(f"Order request received: {payload}")
    logging.debug(f"app.state.quantity: {request.app.state.quantity}")

    symbol = payload.get("symbol", "DUMMY").upper()
    if symbol != "DUMMY":
        settings = get_settings()

        order_details = {
            "symbol": symbol,
            "quantity": request.app.state.quantity,
            "disclosed_quantity": 0,
            "exchange": settings["option_exchange"],
            "tag": payload.pop("tag", "no_tag"),
            "side": "BUY",
        }

        exit_price = payload.pop("exit_price")
        cost_price = payload.pop("cost_price")
        order_details.update(payload)

        order_id = Helper.one_side(order_details)
        if order_id:
            order_details["entry_id"] = order_id
            order_details["exit_price"] = exit_price
            order_details["target_price"] = cost_price + settings["profit"]
            if order_details["tag"] != "no_tag":
                order_details["target_price"] = cost_price + (cost_price - exit_price)

            order_type = order_details.get("order_type", "LIMIT")
            if order_type == "SL":
                Helper.cancel_orders(symbol, keep_order_id=order_id)
            else:
                Helper.cancel_orders(symbol, keep_order_id=order_id, side="BUY")

            blacklist = ["side", "price", "trigger_price", "order_type"]
            for key in blacklist:
                order_details.pop(key, None)
            O_FUTL.write_file(filepath=TRADE_JSON, content=order_details)
            return JSONResponse(
                content={
                    "message": f"Buy order initiated for {symbol}",
                    "status": "success",
                    "order": order_details,
                }
            )

        return JSONResponse(
            content={
                "message": "error while buy order",
                "status": "failed",
                "order": order_details,
            }
        )


@app.get("/api/trade/sell")
async def reset(symbol: str = "") -> JSONResponse:
    Helper.close_all_for_symbol(symbol, ltp)
    return JSONResponse(
        content={
            "message": "reset completed",
            "status": "success",
        }
    )


# --- SSE Endpoint for Streaming Candlesticks ---
@app.get("/sse/candlesticks/{symbol}")
async def sse_candlestick_endpoint(
    symbol: str, request: Request
) -> EventSourceResponse:
    logging.debug(f"SSE connection requested for symbol: {symbol}")

    last_sent_candle: Optional[Dict[str, Any]] = None

    async def event_generator():
        nonlocal last_sent_candle
        ws = request.app.state.ws
        token_symbols = request.app.state.tokens_nearest

        try:
            token_symbol = [k for k, v in token_symbols.items() if v == symbol][0]
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
                candle_time = current_timestamp_ist - (
                    current_timestamp_ist % CANDLESTICK_TIMEFRAME_SECONDS
                )

                if last_sent_candle is None or candle_time > last_sent_candle["time"]:
                    if last_sent_candle is not None:
                        yield {
                            "event": "live_update",
                            "data": json.dumps(last_sent_candle),
                        }

                    last_sent_candle = {
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "volume": 0,
                        "time": candle_time,
                    }
                else:
                    last_sent_candle["high"] = max(last_sent_candle["high"], price)
                    last_sent_candle["low"] = min(last_sent_candle["low"], price)
                    last_sent_candle["close"] = price

                yield {"event": "live_update", "data": json.dumps(last_sent_candle)}

            except Exception as e:
                continue

    return EventSourceResponse(event_generator())


@app.get("/sse/orders")
async def stream_all_orders(request: Request) -> EventSourceResponse:
    async def event_generator():
        while True:
            ws = request.app.state.ws
            if ws.order_updates:
                order_msg = ws.order_updates.popleft()
                msg_str = json.dumps(order_msg)
                logging.debug(f"SSE sending order_msg: {order_msg}")
                yield {"event": "order_msg", "data": msg_str}
            else:
                await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())


@app.post("/api/admin/restart")
async def restart_trading_session(request: Request) -> JSONResponse:
    """
    Restart the trading session (soft restart).
    """
    try:
        await trading_session_stop(request.app)
        await trading_session_start(request.app)
        return JSONResponse(
            content={"message": "Trading session restarted", "status": "success"}
        )
    except Exception as e:
        return JSONResponse(
            content={"message": f"Failed to restart: {e}", "status": "error"},
            status_code=500,
        )


@app.post("/api/admin/stop")
async def stop_trading_session(request: Request) -> JSONResponse:
    """
    Stop the trading session.
    """
    try:
        await trading_session_stop(request.app)
        return JSONResponse(
            content={"message": "Trading session stopped", "status": "success"}
        )
    except Exception as e:
        return JSONResponse(
            content={"message": f"Failed to stop: {e}", "status": "error"},
            status_code=500,
        )


@app.post("/api/admin/start")
async def start_trading_session(request: Request) -> JSONResponse:
    """
    Start the trading session.
    """
    try:
        await trading_session_start(request.app)
        return JSONResponse(
            content={"message": "Trading session started", "status": "success"}
        )
    except Exception as e:
        return JSONResponse(
            content={"message": f"Failed to start: {e}", "status": "error"},
            status_code=500,
        )


@app.get("/api/admin/settings")
async def get_settings_file() -> JSONResponse:
    """
    Get current settings.yml content.
    """
    try:
        settings_path = Path(S_DATA) / "settings.yml"
        with open(settings_path, "r") as f:
            content = f.read()
        return JSONResponse(content={"content": content, "status": "success"})
    except Exception as e:
        return JSONResponse(
            content={"message": str(e), "status": "error"}, status_code=500
        )


@app.post("/api/admin/settings")
async def update_settings(
    request: Request, settings_data: Dict[str, Any] = Body(...)
) -> JSONResponse:
    """
    Update settings.yml content and stop trading session.
    Scheduler will restart based on schedule.
    """
    try:
        settings_path = Path(S_DATA) / "settings.yml"
        content = settings_data.get("content", "")
        with open(settings_path, "w") as f:
            f.write(content)
        
        await trading_session_stop(request.app)
        
        return JSONResponse(
            content={"message": "Settings saved. Trading session stopped.", "status": "success"}
        )
    except Exception as e:
        return JSONResponse(
            content={"message": str(e), "status": "error"}, status_code=500
        )


@app.get("/api/admin/logs")
async def get_logs() -> JSONResponse:
    """
    Get server log file content.
    """
    try:
        log_path = Path(S_DATA) / "log.txt"
        with open(log_path, "r") as f:
            lines = f.readlines()
            content = "".join(lines[-500:])
        return JSONResponse(content={"content": content, "status": "success"})
    except Exception as e:
        return JSONResponse(
            content={"message": str(e), "status": "error"}, status_code=500
        )


@app.get("/api/chart/settings")
async def get_chart_settings() -> JSONResponse:
    """
    Get chart settings (MA configs) from settings.yml.
    """
    try:
        ma = O_SETG.get("ma", [])
        base = O_SETG.get("base", "NIFTY")
        base_settings = O_SETG.get(base, {})
        profit = (
            base_settings.get("profit", 5) if isinstance(base_settings, dict) else 5
        )
        return JSONResponse(
            content={
                "ma": ma,
                "profit": profit,
            }
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/admin/status")
async def get_admin_status(request: Request) -> JSONResponse:
    """
    Get server status and API key.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        hhmm = now_ist.strftime("%H:%M")
        day = now_ist.strftime("%a")

        is_trading = getattr(request.app.state, "is_trading", False)
        
        hour = now_ist.hour
        minute = now_ist.minute
        # Hardcoded schedule: 9:15 to 23:59
        within_trading_hours = (hour > 9 or (hour == 9 and minute >= 15)) and hour < 23 or (hour == 23 and minute < 59)
        is_trading = within_trading_hours and day in ["Mon", "Tue", "Wed", "Thu", "Fri"]

        return JSONResponse(
            content={
                "status": "running",
                "api_key": O_CNFG.get("api_secret", ""),
                "message": "Server is running. Use admin endpoints to manage settings.",
                "current_time_utc": now_utc.strftime("%H:%M %Z"),
                "current_time_ist": hhmm,
                "day_of_week": day,
                "is_trading": is_trading,
                "within_trading_hours": within_trading_hours,
            }
        )
    except Exception as e:
        import traceback
        return JSONResponse(content={"error": str(e), "trace": traceback.format_exc()}, status_code=500)
