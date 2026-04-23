# main.py
from __future__ import annotations
from src.api import Helper
from src.constants import (
    O_SETG,
    O_CNFG,
    logging,
    O_FUTL,
    TRADE_JSON,
    S_DATA,
    HTPASSWD_FILE,
)
from functools import lru_cache
import pandas as pd
from fastapi import FastAPI, Body, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import time
import json
import os
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
from datetime import datetime, timezone, timedelta
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

    Helper.close_positions()
    logging.info("✅ Trading session stopped.")


def schedule_trading_session(app: FastAPI):
    """Schedule trading session start/stop based on market hours."""
    # Clear existing jobs if any
    for job_id in ["start_session", "stop_session"]:
        try:
            SCHEDULER.remove_job(job_id)
        except Exception:
            pass

    SCHEDULER.add_job(
        trading_session_start,
        trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=14),
        id="start_session",
        args=[app],
    )

    SCHEDULER.add_job(
        trading_session_stop,
        trigger=CronTrigger(day_of_week="mon-fri", hour=23, minute=59),
        id="stop_session",
        args=[app],
    )

    logging.info("Trading session scheduled: 09:14-23:59 Mon-Fri IST (TESTING)")


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
        print(f"{e} in aggregating")
        return []


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    base = O_SETG["base"]
    settings = O_SETG[base] | dct_sym[base]
    return settings


def nullify() -> None:
    try:
        orders = Helper.orders()
        if orders:
            for item in orders:
                if (item["status"] == "OPEN") or (item["status"] == "TRIGGER_PENDING"):
                    order_id = item.get("order_id", None)
                    logging.info(f"cancelling open order {order_id}")
                    Helper.api().order_cancel(order_id)
                    break

        Helper.close_positions()
    except Exception as e:
        logging.error(f"Error in nullify: {e}")
        print_exc()


# --- Application Lifespan Event ---
# Server runs 24/7, scheduler handles trading session
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule trading start/stop (hardcoded: 9:14-23:59 Mon-Fri)
    schedule_trading_session(app)
    SCHEDULER.start()
    logging.info("✅ Scheduler started.")

    # Start trading session immediately (always, for testing)
    await trading_session_start(app)

    yield

    # Shutdown: stop scheduler and trading session
    await trading_session_stop(app)
    SCHEDULER.shutdown()
    logging.info("✅ Scheduler shutdown.")


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
        <html>
        <head><title>Scalper-UMA</title></head>
        <body style="font-family:Arial;text-align:center;padding-top:100px;background:#1a1a2e;color:#fff;">
            <h1>Application is on scheduled sleep</h1>
            <p>Trading hours: 09:14 - 23:59 IST</p>
            <p>Will resume automatically when market opens.</p>
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


@app.get("/api/positions/summary")
async def get_positions_summary() -> JSONResponse:
    """
    Returns positions summary: active positions, order count, m2m, realized pnl.
    """
    try:
        api = Helper.api()
        if not api:
            raise Exception("Helper.api() returned None")
        positions = api.positions or []
        orders = api.broker.get_order_book() or []

        active_positions = [p for p in positions if p and p.get("quantity", 0) != 0]

        valid_orders = [o for o in orders if o and o.get("norenordno")]
        total_orders = len(valid_orders)

        active_orders_count = 0
        for o in valid_orders:
            status = o.get("status", "")
            if status in ["OPEN", "PENDING", "TRIGGER_PENDING"]:
                active_orders_count += 1

        m2m = 0.0
        realized = 0.0
        for pos in positions:
            if pos:
                qty = pos.get("quantity", 0)
                if qty != 0:
                    m2m += pos.get("urmtom", 0)
                realized += pos.get("rpnl", 0)

        return JSONResponse(
            content={
                "positions": active_positions,
                "position_count": len(active_positions),
                "active_orders": active_orders_count,
                "order_count": total_orders,
                "m2m": round(m2m, 2),
                "realized_pnl": round(realized, 2),
            }
        )
    except Exception as e:
        logging.error(f"Error getting positions summary: {e}")
        return JSONResponse(
            content={
                "positions": [],
                "position_count": 0,
                "active_orders": 0,
                "order_count": 0,
                "m2m": 0.0,
                "realized_pnl": 0.0,
            }
        )


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

    nullify()
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
                Helper.cancel_all_orders(symbol, order_id)
            else:
                Helper.cancel_other_orders(symbol, order_id, "BUY")

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
    if symbol:
        logging.info(f"Sell request for symbol: {symbol}")
        nullify()
        return JSONResponse(
            content={
                "message": f"reset completed for {symbol}",
                "status": "success",
            }
        )
    else:
        nullify()
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
    print(f"[{time.time()}] SSE connection requested for symbol: {symbol}")

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
        last_msg = ""
        while True:
            await asyncio.sleep(0.5)
            try:
                ws = request.app.state.ws
                order_msg = ws.order_update.get("message")
                if order_msg:
                    msg_str = json.dumps(order_msg)
                    if msg_str != last_msg:
                        last_msg = msg_str
                        print(order_msg, "/n", "ORDER UPDATE FROM WEBSOCKET")
                        yield {"event": "order_msg", "data": msg_str}
                        orders_cache = Helper.orders()
                        valid_orders = [
                            o for o in orders_cache if o and o.get("order_id")
                        ]
                        if valid_orders:
                            yield {
                                "event": "order_update",
                                "data": json.dumps(orders_cache),
                            }

            except Exception as e:
                print("Order SSE error:", e)

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
    Update settings.yml content and restart trading session.
    """
    try:
        settings_path = Path(S_DATA) / "settings.yml"
        content = settings_data.get("content", "")
        with open(settings_path, "w") as f:
            f.write(content)
        touch_marker()
        logging.info("Settings saved, stopping trading session...")
        try:
            await trading_session_stop(request.app)
            logging.info("Trading session stopped successfully.")
        except Exception as e:
            logging.error(f"Error in trading_session_stop: {e}")
            import traceback

            logging.error(traceback.format_exc())
        logging.info("Starting trading session...")
        try:
            await trading_session_start(request.app)
            logging.info("Trading session started successfully.")
        except Exception as e:
            logging.error(f"Error in trading_session_start: {e}")
            import traceback

            logging.error(traceback.format_exc())
        return JSONResponse(
            content={
                "message": "Settings saved. Trading session restarted.",
                "status": "success",
            }
        )
    except Exception as e:
        logging.error(f"Error in update_settings: {e}")
        import traceback

        logging.error(traceback.format_exc())
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
async def get_status() -> JSONResponse:
    """
    Get server status and API key.
    """
    return JSONResponse(
        content={
            "status": "running",
            "api_key": O_CNFG.get("api_secret", ""),
            "message": "Server is running. Use admin endpoints to manage settings.",
        }
    )
