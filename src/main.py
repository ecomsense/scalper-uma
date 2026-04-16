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
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import time
import json
import subprocess
import os
from src.tickrunner import TickRunner
from src.wserver import Wserver

from sse_starlette.sse import EventSourceResponse
from src.strategy import Strategy
from src.constants import dct_sym
from traceback import print_exc
from contextlib import asynccontextmanager

from pytz import timezone as tz
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != JWT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

IST = tz("Asia/Kolkata")

CANDLESTICK_TIMEFRAME_SECONDS: int = 60
CANDLESTICK_TIMEFRAME_STR: str = "1min"

IST_OFFSET: timedelta = timedelta(hours=5, minutes=30)


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
        candlesticks["time"] = (
            candlesticks.index.astype("int64") // 10**9
        )

        return candlesticks.reset_index(drop=True).to_dict(orient="records")
    except Exception as e:
        print(f"{e} in aggregating")
        return []


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    base = O_SETG["trade"]["base"]
    return O_SETG[base] | dct_sym[base]


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
# We use asynccontextmanager to define the startup and shutdown logic.
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        api = Helper.api()
        user_settings = get_settings()

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
        logging.info(f"Got LTP for {user_settings['base']}: {ltp_of_underlying}")

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

        runner = TickRunner(ws, tokens_nearest)
        task = asyncio.create_task(runner.run())
        app.state.runner_task = task

        print(tokens_nearest, "nearest")
        print("✅ TickRunner started.")

        yield

    finally:
        print("Shutting down...")
        if hasattr(app.state, "runner_task"):
            app.state.runner_task.cancel()
            try:
                await app.state.runner_task
            except asyncio.CancelledError:
                print("✅ TickRunner task cancelled.")
        Helper.close_positions()
        print("✅ Shutdown complete.")


# --- FastAPI App Initialization ---
# Pass the lifespan function to the FastAPI constructor
app = FastAPI(lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/", include_in_schema=False)
async def serve_root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/symbols")
async def get_available_symbols(request: Request) -> JSONResponse:
    """
    Returns a list of available symbols.
    """
    symbols = list(request.app.state.tokens_nearest.values())
    return JSONResponse(content=symbols)


@app.post("/api/trade/buy")
async def place_buy_order(payload: Dict[str, Any] = Body(...), _: str = Depends(verify_api_key)) -> JSONResponse:
    nullify()

    symbol = payload.get("symbol", "DUMMY").upper()
    if symbol != "DUMMY":
        settings = get_settings()

        order_details = {
            "symbol": symbol,
            "quantity": settings["quantity"],
            "disclosed_quantity": 0,
            "exchange": settings["option_exchange"],
            "tag": payload.pop("tag", "no_tag"),
            "side": "BUY",
        }
        # logging.info(payload)

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
async def reset(_: str = Depends(verify_api_key)):
    nullify()
    return JSONResponse(
        content={
            "message": "reset completed",
            "status": "success",
        }
    )


# --- SSE Endpoint for Streaming Candlesticks ---
@app.get("/sse/candlesticks/{symbol}")
async def sse_candlestick_endpoint(symbol: str, request: Request) -> EventSourceResponse:
    print(f"[{time.time()}] SSE connection requested for symbol: {symbol}")

    last_sent_candle: Optional[Dict[str, Any]] = None

    async def event_generator():
        nonlocal last_sent_candle
        while True:
            await asyncio.sleep(0.5)

            ws = request.app.state.ws
            token_symbols = request.app.state.tokens_nearest

            try:
                token_symbol = [k for k, v in token_symbols.items() if v == symbol][0]
                price = ws.ltp[token_symbol]
            except (KeyError, IndexError):
                continue

            ist_now = datetime.now(timezone.utc) + IST_OFFSET
            current_timestamp_ist = int(ist_now.timestamp())

            candle_time = current_timestamp_ist - (
                current_timestamp_ist % CANDLESTICK_TIMEFRAME_SECONDS
            )

            if last_sent_candle is None or candle_time > last_sent_candle["time"]:
                if last_sent_candle is not None:
                    yield {"event": "live_update", "data": json.dumps(last_sent_candle)}

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

    return EventSourceResponse(event_generator())


@app.get("/sse/orders")
async def stream_all_orders(request: Request) -> EventSourceResponse:
    async def event_generator():
        while True:
            await asyncio.sleep(1.5)
            try:
                ws = request.app.state.ws
                print(ws.order_update, "/n", "ORDER UPDATE FROM WEBSOCKET")
                orders_cache = Helper.get_orders()
                yield {"event": "order_update", "data": json.dumps(orders_cache)}

            except Exception as e:
                print("Order SSE error:", e)
                yield {
                    "event": "order_update",
                    "data": json.dumps([]),
                }

    return EventSourceResponse(event_generator())


@app.post("/api/admin/restart")
async def restart_server() -> JSONResponse:
    """
    Restart the uvicorn server via systemd.
    """
    try:
        subprocess.run("systemctl restart uma-scalper", shell=True, check=True)
        return JSONResponse(content={"message": "Server restarting...", "status": "success"})
    except subprocess.CalledProcessError as e:
        return JSONResponse(content={"message": f"Failed to restart: {e}", "status": "error"}, status_code=500)


@app.post("/api/admin/stop")
async def stop_server() -> JSONResponse:
    """
    Stop the uvicorn server via systemd.
    """
    try:
        subprocess.run("systemctl stop uma-scalper", shell=True, check=True)
        return JSONResponse(content={"message": "Server stopped", "status": "success"})
    except subprocess.CalledProcessError as e:
        return JSONResponse(content={"message": f"Failed to stop: {e}", "status": "error"}, status_code=500)


@app.post("/api/admin/start")
async def start_server() -> JSONResponse:
    """
    Start the uvicorn server via systemd.
    """
    try:
        subprocess.run("systemctl start uma-scalper", shell=True, check=True)
        return JSONResponse(content={"message": "Server started", "status": "success"})
    except subprocess.CalledProcessError as e:
        return JSONResponse(content={"message": f"Failed to start: {e}", "status": "error"}, status_code=500)


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
        return JSONResponse(content={"message": str(e), "status": "error"}, status_code=500)


@app.post("/api/admin/settings")
async def update_settings(settings_data: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Update settings.yml content and restart server.
    """
    try:
        settings_path = Path(S_DATA) / "settings.yml"
        content = settings_data.get("content", "")
        with open(settings_path, "w") as f:
            f.write(content)
        subprocess.run("systemctl stop uma-scalper", shell=True, check=True)
        subprocess.run("systemctl start uma-scalper", shell=True, check=True)
        return JSONResponse(content={"message": "Settings saved. Server restarting...", "status": "success"})
    except Exception as e:
        return JSONResponse(content={"message": str(e), "status": "error"}, status_code=500)


@app.get("/api/admin/status")
async def get_status() -> JSONResponse:
    """
    Get server status and API key.
    """
    return JSONResponse(content={
        "status": "running",
        "api_key": O_CNFG.get("api_secret", ""),
        "message": "Server is running. Use admin endpoints to manage settings."
    })
