# SPEC.md Q&A for Scalper-UMA Project

## Architecture

**Q: What is the high-level architecture?**
A: Controller (main.py) handles scheduling, auth, routing. Logic app handles trading. State managed via LogicState singleton.

**Q: What are the main components?**
A: TickRunner (trade execution), Strategy (ATM selection), Wserver (websocket), Helper.api() (broker API)

**Q: What is the state management approach?**
A: LogicState singleton in src/state.py holds: running, paused, ws, runner, tokens_nearest, quantity, started_at

## API Routes

**Q: What are the key API routes?**
A:
- `/api/logic/start` - Start trading session
- `/api/logic/stop` - Stop trading session
- `/api/logic/status` - Get running state
- `/api/summary` - Positions, orders, M2M, realized PnL
- `/api/schedule` - Schedule info
- `/sse/candlesticks/{symbol}` - Live OHLC candles
- `/sse/orders` - Order updates stream

**Q: What authentication is used?**
A: HTTP Basic Auth (configured in main.py)

## External Integrations

**Q: What broker API is used?**
A: Finvasia/Shoonya (Flattrade) - via `src/api.py` Helper class

**Q: How does websocket work?**
A: Wserver connects to broker, subscribes to tokens, pushes LTP updates to `ws.ltp` dict

**Q: What is the session management?**
A: 7-hour TTL on API session to handle broker token rotation

## Configuration

**Q: Where is config stored?**
A: `data/settings.yml` - program times, trade params (quantity, profit, premium), log settings

**Q: What are the schedule times?**
A: Start: 09:15 IST, End: 15:31 IST, Days: Mon-Fri

## Key Files

**Q: What files are critical?**
A:
- `src/main.py` - Controller, routes, SSE endpoints
- `src/logic_app.py` - Start/stop trading session
- `src/state.py` - LogicState singleton
- `src/api.py` - Broker API wrapper
- `src/wserver.py` - Websocket manager
- `src/tickrunner.py` - Trade execution state machine
- `src/strategy.py` - ATM selection, premium matching

## Known Issues

**Q: What are the documented issues?**
A: See AGENTS.md "Known Issues & Fixes" section - includes SSE dict keys, cancel button status, order_cancel kwargs, etc.

## Deployment

**Q: How is it deployed?**
A: Manual uvicorn start (not systemd), PID lock to prevent multiple instances

**Q: Where are logs written?**
A: `data/log.txt` with log.show: true in settings.yml