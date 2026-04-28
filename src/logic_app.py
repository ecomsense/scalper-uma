# Logic App - Trading logic (no changes to core trading components)
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.api import Helper
from src.constants import O_FUTL, S_DATA, TRADE_JSON, access_cnfg, logging
from src.state import _logic_state, get_logic_state

IST_OFFSET = timedelta(hours=5, minutes=30)


def load_template(name: str) -> str:
    template_path = Path(__file__).parent.parent / 'templates' / f'{name}.html'
    if template_path.exists():
        return template_path.read_text()
    return f'<html><body>Template {name} not found</body></html>'


# ============================================================
# Lifecycle Hooks
# ============================================================

def on_start(startup_data: dict, app_data: dict) -> None:
    logging.info('[LIFECYCLE] ============================================')
    logging.info('[LIFECYCLE] Starting trading session...')
    logging.info(f"[LIFECYCLE] Symbol: {startup_data.get('symbol', 'unknown')}")
    logging.info('[LIFECYCLE] ============================================')


def on_stop(app_data: dict) -> None:
    logging.info('[LIFECYCLE] on_stop called - cleaning up')
    pass


# ============================================================
# Settings Loader
# ============================================================

def get_settings() -> dict[str, Any]:
    from src.constants import O_SETG, dct_sym
    
    base = O_SETG.get('base', 'NIFTY')
    return O_SETG.get(base, {}) | dct_sym.get(base, {})


# ============================================================
# Trading Logic (moved from main.py)
# ============================================================

async def trading_session_start(app: Any) -> None:
    logging.info('🔄 Starting trading session...')
    
    if _logic_state.is_running():
        logging.info('Already running, skipping start')
        return

    O_FUTL.write_file(TRADE_JSON, {'entry_id': ''})

    try:
        logging.info('📡 Creating broker API session...')
        api = Helper.api()
        logging.info('✅ Broker API session created')

        settings = get_settings()
        index_token = f"{settings.get('exchange')}|{settings.get('token')}"
        
        from src.wserver import Wserver
        logging.info(f'🔌 Creating websocket for token: {index_token}')
        ws = Wserver(api, [index_token])
        logging.info(f'✅ Websocket created, socket_opened={ws.socket_opened}')

        max_wait = 60
        waited = 0
        logging.info(f'⏳ Waiting for LTP (max {max_wait/2} seconds)...')
        while not ws.ltp and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 1
            if waited % 10 == 0:
                logging.info(f'⏳ Still waiting... waited={waited/2}s, ltp={ws.ltp}, socket_opened={ws.socket_opened}')

        if not ws.ltp:
            logging.error(f'❌ Failed to get LTP from websocket! ws.ltp={ws.ltp}, socket_opened={ws.socket_opened}')
            return

        ltp_of_underlying = next(iter(ws.ltp.values()))

        from src.strategy import Strategy
        sgy = Strategy(settings, ltp_of_underlying)
        tokens = list(sgy.tokens_for_all_trading_symbols.keys())

        if not tokens:
            logging.warning('No tokens found for options')
            return

        all_tokens = [*tokens, index_token]
        logging.info(f'📡 Subscribing to {len(all_tokens)} tokens: {all_tokens[:3]}...')
        ws.subscribe(all_tokens)

        waited = 0
        while len(ws.ltp) < len(all_tokens) and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 1

        symbol_nearest_to_premium: list[str] = []
        for ce_or_pe in ['CE', 'PE']:
            res = sgy.find_trading_symbol_by_atm(ce_or_pe, ws.ltp)
            if res:
                symbol_nearest_to_premium.append(res)

        tokens_nearest: dict[str, str] = sgy.sym.find_wstoken_from_tradingsymbol(symbol_nearest_to_premium)

        from src.tickrunner import TickRunner
        runner = TickRunner(ws, tokens_nearest)
        
        _logic_state.ws = ws
        _logic_state.runner = runner
        _logic_state.tokens_nearest = tokens_nearest
        _logic_state.quantity = settings.get('lots', 1) * sgy.sym.get_lot_size()
        _logic_state.startup_data = settings
        _logic_state.app_data = {}
        _logic_state.running = True
        _logic_state.started_at = datetime.now()
        
        task = asyncio.create_task(runner.run())
        _logic_state.runner_task = task
        
        logging.info(f'Nearest symbols: {tokens_nearest}')
        logging.info('✅ Trading session started.')

    except Exception as e:
        logging.error(f'Failed to start trading session: {e}')
        import traceback
        logging.error(traceback.format_exc())


async def trading_session_stop(app: Any) -> None:
    logging.info('Stopping trading session...')

    if _logic_state.runner_task:
        _logic_state.runner_task.cancel()
        try:
            await _logic_state.runner_task
        except asyncio.CancelledError:
            logging.info('TickRunner task cancelled.')
        except Exception:
            pass

    _logic_state.reset()
    logging.info('✅ Trading session stopped.')


# ============================================================
# Start/Stop/Pause Functions (API layer)
# ============================================================

async def start_logic() -> dict[str, Any]:
    if _logic_state.is_running():
        return {'status': 'already_running', 'message': 'Trading is already running'}
    
    await trading_session_start(None)
    
    return {
        'status': 'started',
        'message': 'Trading session started',
        'started_at': _logic_state.started_at.isoformat() if _logic_state.started_at else None,
    }


async def stop_logic() -> dict[str, Any]:
    if not _logic_state.running:
        return {'status': 'already_stopped', 'message': 'Trading is not running'}
    
    await trading_session_stop(None)


async def pause_logic(reason: str = 'manual', duration_seconds: int = 60) -> dict[str, Any]:
    if _logic_state.is_running():
        await trading_session_stop(None)
    
    _logic_state.paused = True
    _logic_state.pause_until = datetime.now() + timedelta(seconds=duration_seconds)
    _logic_state.pause_reason = reason
    
    return {
        'status': 'paused',
        'reason': reason,
        'until': _logic_state.pause_until.isoformat(),
    }


def get_status() -> dict[str, Any]:
    return {
        'running': _logic_state.is_running(),
        'started_at': _logic_state.started_at.isoformat() if _logic_state.started_at else None,
        'paused': _logic_state.is_paused(),
        'pause_reason': _logic_state.pause_reason if _logic_state.is_paused() else '',
        'quantity': _logic_state.quantity,
        'symbols': list(_logic_state.tokens_nearest.values()),
    }


# ============================================================
# Router
# ============================================================

def create_logic_router() -> APIRouter:
    router = APIRouter(tags=['logic'])

    @router.get('/status')
    async def status():
        return get_status()

    @router.post('/start')
    async def start():
        return await start_logic()

    @router.post('/stop')
    async def stop():
        return await stop_logic()

    @router.post('/pause')
    async def pause(reason: str = 'manual', duration: int = 60):
        return await pause_logic(reason=reason, duration_seconds=duration)

    return router