# main.py
from src.api import Helper
from src.constants import (
    O_SETG,
    logging,
    O_FUTL,
    TICK_CSV_PATH,
    TRADE_JSON,
)
from functools import lru_cache
import pandas as pd
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import time
import json
from src.tickrunner import TickRunner
from src.wserver import Wserver

from sse_starlette.sse import EventSourceResponse
from src.strategy import Strategy
from src.constants import dct_sym
from traceback import print_exc
from contextlib import asynccontextmanager

from pytz import timezone as tz
from datetime import datetime, timezone, timedelta

IST = tz("Asia/Kolkata")

CANDLESTICK_TIMEFRAME_SECONDS = 60  # 1 minute
CANDLESTICK_TIMEFRAME_STR = "1min"

# Define the Indian Standard Time (IST) offset
IST_OFFSET = timedelta(hours=5, minutes=30)

# --- Helper Functions for Candlestick Aggregation ---
def aggregate_ticks_to_candlesticks(
    df: pd.DataFrame, timeframe_str: str = CANDLESTICK_TIMEFRAME_STR
) -> list[dict]:
    """
    Aggregates a DataFrame of ticks into OHLCV candlesticks using pandas.
    """
    try:
        if df.empty:
            return []

        # Ensure timestamp is a DatetimeIndex
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
            candlesticks.index.astype('int64') // 10**9
        )  # Unix timestamp in seconds


        return candlesticks.reset_index(drop=True).to_dict(orient="records")
    except Exception as e:
        print(f"{e} in aggregating")


async def get_all_candlesticks_for_symbol(symbol: str) -> list[dict]:
    """
    TO BE REMOVED
    """
    try:
        # Load the entire CSV for aggregation
        full_df = pd.read_csv(
            TICK_CSV_PATH,
            names=["timestamp", "symbol", "price", "volume"],
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        symbol_df = full_df[full_df["symbol"] == symbol.upper()]
        # print(symbol_df.head()) # Keep this for debugging if needed, but usually remove

        # Aggregate and return
        all_candles = aggregate_ticks_to_candlesticks(symbol_df)
        return all_candles
    except FileNotFoundError:
        print(f"[{time.time()}] CSV file not found at {TICK_CSV_PATH}.")
        return []
    except Exception as e:
        print(f"[{time.time()}] Error loading/aggregating data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing data: {e}")
    

@lru_cache(maxsize=1)
def get_settings():
    # return json response from dictionary
    base = O_SETG["trade"]["base"]
    return O_SETG[base] | dct_sym[base]


def nullify():
    try:
        # nullify orders
        orders = Helper.get_orders()
        if orders:
            for item in orders:
                if (item["status"] == "OPEN") or (
                    item["status"] == "TRIGGER_PENDING"
                ):
                    order_id = item.get("order_id", None)
                    logging.info(f"cancelling open order {order_id}")
                    Helper.api().order_cancel(order_id)
                else:
                    print()
            Helper.close_positions()
    except Exception as e:
        logging.error(f"Error in nullify: {e}")
        print_exc()


# --- Application Lifespan Event ---
# We use asynccontextmanager to define the startup and shutdown logic.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This block runs on application startup
    try:
        api = Helper.api()
        user_settings = get_settings()
        ltp_of_underlying = Helper.ltp(user_settings["exchange"], user_settings["token"])
        sgy = Strategy(user_settings, ltp_of_underlying)
        tokens = list(sgy.tokens_for_all_trading_symbols.keys())
        ws = Wserver(api, tokens)

        while not ws.ltp:
            await asyncio.sleep(0.5)

        symbol_nearest_to_premium = []
        for ce_or_pe in ["CE", "PE"]:
            res = sgy.find_trading_symbol_by_atm(ce_or_pe, ws.ltp)
            symbol_nearest_to_premium.append(res)

        tokens_nearest: dict = sgy.sym.find_wstoken_from_tradingsymbol(symbol_nearest_to_premium)

        # add application state
        app.state.tokens_nearest = tokens_nearest
        app.state.ws = ws

        runner = TickRunner(ws, tokens_nearest)
        # Start the runner task and hold a reference if needed for shutdown
        task = asyncio.create_task(runner.run())
        app.state.runner_task = task # Store task on app.state to manage later

        print(tokens_nearest, "nearest")
        print("✅ TickRunner started.")

        # This `yield` is essential! It tells FastAPI that the startup is complete
        # and it can begin serving requests.
        yield

    # This block runs on application shutdown
    finally:
        print("Shutting down...")
        if hasattr(app.state, 'runner_task'):
            app.state.runner_task.cancel() # Cancel the task
            try:
                await app.state.runner_task # Wait for it to finish canceling
            except asyncio.CancelledError:
                print("✅ TickRunner task cancelled.")
        Helper.close_positions() # A good place to close any open positions
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
async def place_buy_order(payload: dict = Body(...)) -> JSONResponse:
    nullify()
    symbol = payload.get("symbol", "DUMMY").upper()
    if symbol != "DUMMY":
        settings = get_settings()

        order_details = {
            "symbol": symbol,
            "quantity": settings["quantity"],
            "disclosed_quantity": 0,
            "exchange": settings["option_exchange"],
            "tag": "uma_scalper",
            "side": "BUY",
        }
        print(payload)
        exit_price = payload.pop("exit_price")
        cost_price = payload.pop("cost_price")
        order_details.update(payload)

        order_id = Helper.one_side(order_details)
        if order_id:
            order_details["entry_id"] = order_id
            order_details["exit_price"] = exit_price
            order_details["target_price"] = cost_price + settings["profit"]
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
async def reset():
    nullify()
    return JSONResponse(
        content={
            "message": "reset completed",
            "status": "success",
        }
    )


# --- SSE Endpoint for Streaming Candlesticks ---
@app.get("/sse/candlesticks/{symbol}")
async def sse_candlestick_endpoint(symbol: str, request: Request):
    symbol = symbol.upper()
    print(f"[{time.time()}] SSE connection requested for symbol: {symbol}")

    # Use a dictionary to store the state of the in-progress candlestick
    last_sent_candle = None

    async def event_generator():
        nonlocal last_sent_candle # Allow modifying the outer scope variable
        while True:
            await asyncio.sleep(0.5)
            
            ws = request.app.state.ws
            token_symbols = request.app.state.tokens_nearest
            
            try:
                token_symbol = [k for k, v in token_symbols.items() if v == symbol][0]
                price = ws.ltp[token_symbol]
            except (KeyError, IndexError):
                # Symbol not found or price not available yet
                continue

            # Calculate the current time in IST
            ist_now = datetime.now(timezone.utc) + IST_OFFSET
            # Convert to a Unix timestamp
            current_timestamp_ist = int(ist_now.timestamp())

            # Round down to the nearest minute to get the candle timestamp
            candle_time = current_timestamp_ist - (current_timestamp_ist % CANDLESTICK_TIMEFRAME_SECONDS)
                
            if last_sent_candle is None or candle_time > last_sent_candle["time"]:
                # New candle started, send the last one and create a new one
                if last_sent_candle is not None:
                    # Send the completed candle for the previous period
                    yield {"event": "live_update", "data": json.dumps(last_sent_candle)}

                # Initialize the new candle
                last_sent_candle = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 0,
                    "time": candle_time,
                }
            else:
                # Update the existing candle
                last_sent_candle["high"] = max(last_sent_candle["high"], price)
                last_sent_candle["low"] = min(last_sent_candle["low"], price)
                last_sent_candle["close"] = price
                # Send the updated candle for the current period
                yield {"event": "live_update", "data": json.dumps(last_sent_candle)}
                
            
    return EventSourceResponse(event_generator())


@app.get("/sse/orders")
async def stream_all_orders():
    async def event_generator():
        while True:
            await asyncio.sleep(1.5)  # obey rate limits
            try:
                orders_cache = Helper.get_orders()
                yield {"event": "order_update", "data": json.dumps(orders_cache)}

            except Exception as e:
                print("Order SSE error:", e)
                yield {
                    "event": "order_update",
                    "data": json.dumps([]),
                }

    return EventSourceResponse(event_generator())