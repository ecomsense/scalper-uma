# Scalper-UMA Agent Context

## Project Overview

**Scalper-UMA** is a real-time options trading bot built with FastAPI that connects to Finvasia broker API for live options trading.

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `Helper` | `src/api.py` | Broker API wrapper (singleton pattern) |
| `Wserver` | `src/wserver.py` | WebSocket manager for price feeds |
| `TickRunner` | `src/tickrunner.py` | Trade execution state machine |
| `Strategy` | `src/strategy.py` | ATM selection and premium matching |
| `Symbol` | `src/symbol.py` | Symbol/token management |

## Trading Flow

1. App starts → `Helper.api()` creates broker session
2. WebSocket connects via `Wserver` 
3. `TickRunner` monitors prices and executes trades
4. SSE endpoints stream candlesticks and order updates

## Configuration

- **Credentials**: `{project-name}_.yml` (e.g., `scalper-uma.yml`)
- **Settings**: `data/settings.yml`
- **Trade state**: `data/trade.json`

## Common Tasks

- **Add API endpoint**: Add to `src/main.py` with `@app.post/get`
- **Modify trading logic**: Edit `src/strategy.py`
- **Change broker**: Update `broker` in credentials yml

## Important Notes

- The "session" in this codebase refers to the broker API connection (Finvasia)
- No database - uses JSON files for persistence
- Trades NIFTY/BANKNIFTY options based on premium proximity
