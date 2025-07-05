# main.py
from src.api import Helper
from src.constants import O_SETG, logging, O_FUTL, TICK_CSV_PATH, TRADE_JSON
from src.sse_order_client import get_orders
from functools import lru_cache
import pandas as pd
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import time
import json
import uvicorn

from sse_starlette.sse import EventSourceResponse

CANDLESTICK_TIMEFRAME_SECONDS = 60  # 1 minute
CANDLESTICK_TIMEFRAME_STR = "1min"


if O_FUTL.is_file_exists(TRADE_JSON):
    logging.info("deleting trade json")
    O_FUTL.del_file(TRADE_JSON)


# --- Helper Functions for Candlestick Aggregation ---
def aggregate_ticks_to_candlesticks(
    df: pd.DataFrame, timeframe_str: str = CANDLESTICK_TIMEFRAME_STR
) -> list[dict]:
    """
    Aggregates a DataFrame of ticks into OHLCV candlesticks using pandas.
    """
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
        candlesticks.index.astype(int) // 10**9
    )  # Unix timestamp in seconds

    return candlesticks.reset_index(drop=True).to_dict(orient="records")


async def get_all_candlesticks_for_symbol(symbol: str) -> list[dict]:
    """
    Loads all ticks for a symbol from the CSV and aggregates them into candlesticks.
    This function will be called for both initial and live data.
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
    return O_SETG[base]


@lru_cache(maxsize=1)
def get_symbols() -> list[str]:
    df = pd.read_csv(TICK_CSV_PATH, names=["timestamp", "symbol", "price", "volume"])
    return df["symbol"].drop_duplicates().tolist()


def nullify():
    try:
        # nullify orders
        orders = get_orders()
        for item in orders:
            if item and item["status"] == "open":
                print("modify to close")
        Helper.close_positions()
    except Exception as e:
        logging.error(f"Error in nullify: {e}")


# --- FastAPI App Initialization ---
app = FastAPI()


@app.get("/", include_in_schema=False)
async def serve_root():
    return FileResponse(STATIC_DIR / "index.html")


# --- API Endpoints (MUST be defined BEFORE static files mount at root) ---
@app.get("/api/symbols")
async def get_available_symbols() -> JSONResponse:
    """
    Returns a list of available symbols.
    """
    symbols = get_symbols()
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
            "exchange": settings["option_exchange"],
            "tag": "uma_scalper",
            "side": "B",
            "price": payload["high"],
            "trigger_price": payload["high"] + 0.05,
            "order_type": "SL",
        }
        order_id = Helper.api().order_place(**order_details)
        if order_id:
            order_details["order_id"] = order_id
            order_details["exit_price"] = payload["low"]
            order_details["target_price"] = payload["high"] + settings["profit"]
            blacklist = ["side", "price", "trigger_price", "order_type"]
            for key in blacklist:
                del order_details[key]
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
async def sse_candlestick_endpoint(symbol: str):
    nullify()
    symbol = symbol.upper()
    print(f"[{time.time()}] SSE connection requested for symbol: {symbol}")

    async def event_generator():
        # 1. Send initial historical data (reads entire CSV)
        initial_candles = await get_all_candlesticks_for_symbol(symbol)

        yield {"event": "initial_data", "data": json.dumps(initial_candles)}
        print(
            f"[{time.time()}] Sent {len(initial_candles)} initial historical candles via SSE for {symbol}"
        )

        # 2. Stream "live" updates (re-reads and re-aggregates entire CSV periodically)
        # This is inefficient but adheres to the "no tick_processor" constraint
        last_sent_candle_time = 0  # To track what we've already sent

        if initial_candles:
            # If initial data sent, the last one is the latest complete/forming candle
            last_sent_candle_time = initial_candles[-1]["time"]

        while True:
            try:
                # Poll the CSV periodically (e.g., every 1 second)
                await asyncio.sleep(1)

                # Re-read and re-aggregate all data for the symbol
                current_all_candles = await get_all_candlesticks_for_symbol(symbol)

                if not current_all_candles:
                    continue  # No data yet, wait for next poll

                latest_candle = current_all_candles[-1]

                # Only send an update if there's a new candle or the last candle has changed
                # This logic is simplified; a robust system would compare open, high, low, close
                # For now, if the latest candle's time is new, or if it's the same time but updated (via re-aggregation)
                if latest_candle["time"] > last_sent_candle_time or (
                    latest_candle["time"] == last_sent_candle_time
                    and (
                        latest_candle["close"] != initial_candles[-1]["close"]
                        if initial_candles
                        else True
                    )
                ):  # A very basic check

                    yield {"event": "live_update", "data": json.dumps(latest_candle)}
                    last_sent_candle_time = latest_candle["time"]
                    # To keep initial_candles up-to-date with the latest aggregation if needed for future comparisons
                    initial_candles = current_all_candles

            except asyncio.CancelledError:
                print(f"[{time.time()}] SSE event generator for {symbol} cancelled.")
                break
            except Exception as e:
                print(f"[{time.time()}] SSE event generator error for {symbol}: {e}")
                # Log error and continue, don't crash the stream
                await asyncio.sleep(1)  # Prevent tight loop on error

    return EventSourceResponse(event_generator())


@app.get("/sse/orders")
async def stream_all_orders():
    api = Helper.api()
    last_snapshot = []

    async def event_generator():
        nonlocal last_snapshot
        while True:
            await asyncio.sleep(1)  # obey rate limits
            try:
                all_orders = api.orders

                # Optional: avoid flooding frontend with same data
                if all_orders != last_snapshot:
                    last_snapshot = all_orders
                    yield {"event": "order_update", "data": json.dumps(all_orders)}

            except Exception as e:
                print("Order SSE error:", e)
                yield {
                    "event": "order_update",
                    "data": json.dumps([]),
                }

    return EventSourceResponse(event_generator())


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
