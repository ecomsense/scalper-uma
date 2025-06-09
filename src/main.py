from constants import logging, O_SETG, S_DATA
from api import Helper
from toolkit.kokoo import is_time_past, kill_tmux
from traceback import print_exc

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import asyncio
import uvicorn

app = FastAPI()

# In-memory cache for CSV data and aggregated candlesticks
# You might want a more sophisticated caching mechanism (e.g., Redis) for larger scale
symbol_data_cache = {} # Stores raw tick data DataFrames per symbol
candlestick_cache = {} # Stores aggregated candlestick data per symbol/timeframe

# --- Configuration ---
CSV_DIR = S_DATA # Directory where your CSV files are stored
TICK_FILE_PATTERN = "{symbol}_ticks.csv" # e.g., "RELIANCE_ticks.csv"
CANDLESTICK_TIMEFRAME = "1min" # or "5min", "1H", etc.

# --- Helper Function to Read and Aggregate CSV ---
async def read_and_process_ticks(symbol: str):
    file_path = f"{CSV_DIR}{TICK_FILE_PATTERN.format(symbol=symbol)}"
    try:
        # Read the entire CSV for now. For large files, you might need to
        # read only new lines or use a database.
        df = pd.read_csv(
            file_path,
            names=["timestamp", "symbol", "price", "volume"],
            parse_dates=["timestamp"],
            index_col="timestamp"
        )
        df = df[df['symbol'] == symbol] # Filter by symbol if the CSV has multiple
        symbol_data_cache[symbol] = df # Cache raw data
        return df
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"CSV file for symbol {symbol} not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {e}")

def aggregate_to_candlesticks(df: pd.DataFrame, timeframe: str = CANDLESTICK_TIMEFRAME):
    # Ensure the DataFrame is sorted by time
    df = df.sort_index()

    # Resample to the desired timeframe
    ohlc = df['price'].resample(timeframe).ohlc()
    volume = df['volume'].resample(timeframe).sum()

    candlesticks = pd.DataFrame({
        'open': ohlc['open'],
        'high': ohlc['high'],
        'low': olc['low'],
        'close': ohlc['close'],
        'volume': volume
    })

    # Drop rows where no trades occurred (NaN values)
    candlesticks = candlesticks.dropna()

    # Format for JavaScript charting libraries (timestamp in ms or seconds)
    # Lightweight Charts expects time in seconds or datetime string, Plotly in ms
    candlesticks['time'] = (candlesticks.index.astype(int) // 10**9) # Unix timestamp in seconds
    # If you need milliseconds for Plotly:
    # candlesticks['time'] = (candlesticks.index.astype(int) // 10**6)

    return candlesticks.reset_index(drop=True).to_dict(orient="records")

# --- FastAPI Endpoints ---

@app.get("/api/candlesticks/{symbol}")
async def get_candlestick_data(symbol: str):
    """
    Returns aggregated candlestick data for a given symbol.
    """
    symbol = symbol.upper() # Ensure symbol is consistent (e.g., RELIANCE)

    # Check if raw data is already cached, otherwise load from CSV
    if symbol not in symbol_data_cache:
        await read_and_process_ticks(symbol)

    # Aggregate to candlesticks and cache
    if symbol not in candlestick_cache:
      # or \
       # Add logic to check if cached data is stale or if CSV has been updated
       # For simplicity here, we re-aggregate every time, but for real-time you'd
       # want to incrementally update the cache.
        # Placeholder for real-time update check
        raw_df = symbol_data_cache[symbol]
        candlesticks = aggregate_to_candlesticks(raw_df)
        candlestick_cache[symbol] = candlesticks

    return JSONResponse(content=candlestick_cache[symbol])

@app.post("/api/trade/buy")
async def place_buy_order():
    """
    Handles a "Buy" trade request.
    """
    # Implement your trade logic here:
    # - Authenticate user
    # - Connect to broker's trading API
    # - Place buy order
    # - Log the trade
    print("Buy button pressed! Executing buy order...")
    return JSONResponse(content={"message": "Buy order initiated", "status": "success"})

@app.post("/api/trade/sell")
async def place_sell_order():
    """
    Handles a "Sell" trade request.
    """
    # Implement your trade logic here:
    print("Sell button pressed! Executing sell order...")
    return JSONResponse(content={"message": "Sell order initiated", "status": "success"})

# Optional: Endpoint to get available symbols (if you have a list)
@app.get("/api/symbols")
async def get_available_symbols():
    # In a real app, this would dynamically read from your CSV directory
    # or a configuration file.
    return JSONResponse(content=["RELIANCE", "TCS", "INFY"]) # Example

app.mount("/", StaticFiles(directory="static", html=True), name="static")
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
