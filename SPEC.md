# Scalper-UMA Specification

## Project Overview

**Project Name**: Scalper-UMA
**Type**: Options scalping trading bot
**Goal**: Automate intraday option scalping with predefined strategy

## Architecture

```
Controller (main.py) → Logic App → TickRunner → Strategy → Broker API
```

- **Controller**: FastAPI app, scheduling, HTTP auth, routes
- **Logic App**: Trading session management
- **TickRunner**: State machine for trade execution (create → entry → exit → complete)
- **Strategy**: ATM strike selection, premium matching
- **Broker API**: Finvasia/Shroonya (Flattrade) wrapper

## Key Components

| Component | Responsibility |
|-----------|----------------|
| `main.py` | FastAPI app, PID lock, schedule config |
| `logic_app.py` | Start/stop trading session |
| `state.py` | LogicState singleton (running, ws, tokens, etc.) |
| `api.py` | Helper.api() - broker session, 7h TTL |
| `wserver.py` | Websocket manager for live prices |
| `tickrunner.py` | Trade execution state machine |
| `strategy.py` | Option strike selection by ATM/premium |

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Root (sleeping or logic page) |
| `/api/schedule` | GET | Schedule info |
| `/api/logic/start` | POST | Start trading |
| `/api/logic/stop` | POST | Stop trading |
| `/api/logic/status` | GET | Running state |
| `/api/summary` | GET | Positions, orders, PnL |
| `/api/admin/settings` | GET/PUT | config |
| `/sse/candlesticks/{symbol}` | GET | Live OHLC stream |
| `/sse/orders` | GET | Order updates stream |

## Configuration

- **Schedule**: 09:15-15:31 IST, Mon-Fri
- **Session TTL**: 7 hours (broker token rotation)
- **Config file**: `data/settings.yml`

## Dependencies

- fastapi, uvicorn
- flattrade (broker SDK)
- sse-starlette (server-sent events)
- apscheduler (scheduling)
- lightweight-charts (frontend)

## Deployment

- Manual uvicorn start (PID lock prevents duplicates)
- Log file: `data/log.txt`
- No systemd (per project requirements)

## Known Issues to Watch

1. Order cancel status check must handle uppercase statuses
2. order_cancel() API doesn't accept quantity kwarg
3. Use instance variables not class variables for FastAPI state
4. SSE token lookup must check dict values not keys

## Milestones

- [x] Session TTL handling
- [x] Schedule-based auto start/stop
- [x] Responsive UI with charts
- [x] SSE candlesticks streaming
- [x] Order updates via SSE