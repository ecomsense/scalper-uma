# Scalper-UMA - Agent Context

> Operate based on `~/.claude/rules.md` (global rules)
> See [SPEC.md](SPEC.md) for High Level Design (HLD)
> See [BUILD.md](BUILD.md) for implementation details

## Architecture

```
Controller (main.py) → Logic App → TickRunner → Strategy → Broker API
```

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | Controller, ScheduleConfig, routes |
| `src/logic_app.py` | Trading session start/stop |
| `src/state.py` | LogicState singleton |
| `src/api.py` | Helper.api() with session TTL |
| `src/tickrunner.py` | Trade execution state machine |
| `src/strategy.py` | ATM selection, premium matching |
| `src/wserver.py` | WebSocket manager |

## Route Structure

| Path | Description |
|------|-------------|
| `/` | Root - sleeping or logic page based on schedule |
| `/api/logic/start` | Start trading session |
| `/api/logic/stop` | Stop trading session |
| `/api/logic/status` | Running, paused, pause_reason |
| `/api/summary` | Positions, orders, m2m, realized_pnl |
| `/sse/candlesticks/{symbol}` | Live OHLC candles |
| `/sse/orders` | Order updates stream |

## Server

**User**: uma | **Service**: `fastapi_app` (systemd)

```bash
systemctl --user status fastapi_app
systemctl --user restart fastapi_app
journalctl --user -u fastapi_app -n 20
```