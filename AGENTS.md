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

## Server Management

### Server Details
- **IP**: 65.20.83.178
- **User**: uma
- **Service**: fastapi_app.service

### Starting/Stopping Server
```bash
ssh uma@65.20.83.178 "systemctl --user stop fastapi_app.service && sleep 2 && systemctl --user start fastapi_app.service"
```

### Restarting After Code Changes
```bash
# Local: commit and push
cd /home/pannet1/py/fastapi/scalper-uma && git add -A && git commit -m "message" && git push

# Server: pull and restart
ssh uma@65.20.83.178 "cd /home/uma/no_env/uma_scalper && git pull && systemctl --user stop fastapi_app.service && sleep 2 && systemctl --user start fastapi_app.service"
```

### Testing Endpoints
```bash
ssh uma@65.20.83.178 "curl -s http://127.0.0.1:8000/api/chart/settings"
```

### Killing Ghost Processes
If multiple uvicorn processes are running:
```bash
ssh uma@65.20.83.178 "pkill -f uvicorn && sleep 2 && systemctl --user start fastapi_app.service"
```

## Common Tasks

- **Add API endpoint**: Add to `src/main.py` with `@app.post/get`
- **Modify trading logic**: Edit `src/strategy.py`
- **Change broker**: Update `broker` in credentials yml

## Important Notes

- The "session" in this codebase refers to the broker API connection (Finvasia)
- No database - uses JSON files for persistence
- Trades NIFTY/BANKNIFTY options based on premium proximity
- Always use `systemctl --user` for server management
- Delete cached bytecode: `rm -rf src/__pycache__`
- Use `default.target` for user services (not `multi-user.target`)

## Bug Fixes & Discoveries

### Chart Settings Profit (2026-04-22)

**Symptom**: Frontend always showed TGT as buy + 5, ignoring settings.yml profit value.

**Root Cause**: `/api/chart/settings` endpoint only returned `ma` config, not `profit`.

**Fix** (`src/main.py`):
```python
base = O_SETG.get("base", "NIFTY")
base_settings = O_SETG.get(base, {})
profit = base_settings.get("profit", 5)
return JSONResponse(content={"ma": ma, "profit": profit})
```

### Multiple Uvicorn Processes

**Symptom**: Code changes not taking effect despite restart.

**Root Cause**: Multiple uvicorn processes running (old from --reload or direct start).

**Fix**: Always kill all processes before restart:
```bash
pkill -f uvicorn && sleep 2 && systemctl --user start fastapi_app.service
```