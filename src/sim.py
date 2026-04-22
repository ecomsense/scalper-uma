# sim.py - Simulation version of main.py with dummy data (no broker API deps)
from __future__ import annotations
from fastapi import FastAPI, Body, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import time
import json
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from traceback import print_exc
from contextlib import asynccontextmanager

IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET)

CANDLESTICK_TIMEFRAME_SECONDS: int = 60


def generate_dummy_candles(base_price: float = 22000, count: int = 200) -> List[Dict[str, Any]]:
    candles = []
    now = int(datetime.now(IST).timestamp())
    end_time = now - (now % 60)  # Align to minute
    start_time = end_time - count * 60
    price = base_price
    
    # Generate oldest first
    for i in range(count):
        change = (random.random() - 0.5) * 30
        open_price = price
        close_price = price + change
        high = max(open_price, close_price) + random.random() * 10
        low = min(open_price, close_price) - random.random() * 10
        candles.append({
            "time": start_time + i * 60,
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_price, 2),
        })
        price = close_price
    
    # Return newest first (chart.js will reverse it)
    return list(reversed(candles))


class DummyHelper:
    def __init__(self):
        self.positions = []
        self.orders = []
    
    def orders(self):
        return self.orders
    
    def close_positions(self):
        self.positions = []


class DummyWserver:
    def __init__(self):
        self.ltp: Dict[str, float] = {}
        self.order_update: Dict[str, Any] = {}
        self._candle_data: Dict[str, List[Dict]] = {}
        self._last_price: float = 22000
    
    def subscribe(self, tokens: List[str]):
        for token in tokens:
            self.ltp[token] = self._last_price + random.random() * 10
    
    def update_price(self, symbol: str, price: float):
        ws_token = f"NFO|{symbol}"
        self.ltp[ws_token] = price


DummyHelper_INST = DummyHelper()
DummyWs_INST = DummyWserver()


def get_dummy_settings() -> Dict[str, Any]:
    return {
        "base": "NIFTY",
        "symbol": "NIFTY",
        "exchange": "NSE",
        "token": "26000",
        "option_exchange": "NFO",
        "lots": 1,
        "profit": 5,
        "atm_distance": 200,
        "ma": [],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_dummy_settings()
    
    base_price = 22000
    ce_symbol = f"NIFTY28APR26{24000}CE"
    pe_symbol = f"NIFTY28APR26{24000}PE"
    
    tokens_nearest = {
        f"NFO|72458": ce_symbol,
        f"NFO|72459": pe_symbol,
    }
    
    app.state.tokens_nearest = tokens_nearest
    app.state.ws = DummyWs_INST
    app.state.settings = settings
    app.state.base_price = base_price
    
    ce_candles = generate_dummy_candles(base_price)
    pe_candles = generate_dummy_candles(base_price - 200)
    
    app.state.ce_candles = ce_candles
    app.state.pe_candles = pe_candles
    
    print(f"✅ Sim started with {len(ce_candles)} candles")
    print(f"   CE: {ce_symbol}, PE: {pe_symbol}")
    
    yield
    
    print("Shutting down Sim...")


app = FastAPI(lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/", include_in_schema=False)
async def serve_root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/symbols")
async def get_available_symbols(request: Request) -> JSONResponse:
    symbols = list(request.app.state.tokens_nearest.values())
    return JSONResponse(content=symbols)


@app.get("/api/positions/summary")
async def get_positions_summary() -> JSONResponse:
    return JSONResponse(content={
        "positions": 0,
        "position_count": 0,
        "active_orders": 0,
        "order_count": 0,
        "m2m": 0.0,
        "realized_pnl": 0.0,
    })


@app.get("/api/historical/{symbol}")
async def get_historical_data(symbol: str, request: Request) -> JSONResponse:
    try:
        tokens_nearest = request.app.state.tokens_nearest
        ws_token = next((k for k, v in tokens_nearest.items() if v == symbol), None)
        
        if not ws_token:
            return JSONResponse(content={"data": []})
        
        is_pe = "PE" in symbol
        candles = request.app.state.pe_candles if is_pe else request.app.state.ce_candles
        
        return JSONResponse(content={"data": candles})
    except Exception as e:
        print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/trade/buy")
async def place_buy_order(
    request: Request, payload: Dict[str, Any] = Body(...)
) -> JSONResponse:
    symbol = payload.get("symbol", "DUMMY")
    return JSONResponse(content={
        "message": f"Simulated buy for {symbol}",
        "status": "success",
        "order": payload,
    })


@app.get("/api/trade/sell")
async def reset() -> JSONResponse:
    return JSONResponse(content={
        "message": "Simulated reset",
        "status": "success",
    })


@app.get("/sse/candlesticks/{symbol}")
async def sse_candlestick_endpoint(
    symbol: str, request: Request
) -> JSONResponse:
    return JSONResponse(content={"message": "sim mode - no live updates"})


@app.get("/sse/orders")
async def stream_all_orders(request: Request) -> JSONResponse:
    return JSONResponse(content=[])


@app.get("/api/chart/settings")
async def get_chart_settings() -> JSONResponse:
    settings = get_dummy_settings()
    return JSONResponse(content={"ma": settings.get("ma", [])})


@app.get("/api/admin/status")
async def get_status() -> JSONResponse:
    return JSONResponse(content={
        "status": "running",
        "api_key": "sim-key-12345",
        "message": "Sim server running.",
    })


@app.get("/api/admin/settings")
async def get_settings_file() -> JSONResponse:
    dummy_yml = """nifty:
  symbol: NIFTY
  exchange: NSE
  token: "26000"
  option_exchange: NFO
  lots: 1
  profit: 5
  atm_distance: 200
  ma: []
"""
    return JSONResponse(content={"content": dummy_yml, "status": "success"})


@app.post("/api/admin/settings")
async def update_settings(settings_data: Dict[str, Any] = Body(...)) -> JSONResponse:
    return JSONResponse(content={
        "message": "Settings saved (sim)",
        "status": "success",
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)