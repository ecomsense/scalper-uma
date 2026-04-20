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

## Cron Setup

- User-level cron is used (not root)
- Cron script: `factory/cron.py`

### Running systemctl from Python

The key insight: running `/usr/bin/systemctl` directly (without sudo) works from user cron because systemd socket is accessible. Use full path:

```python
import subprocess
import os
os.chdir("/path/to/your/project")
action = "start"  # or "stop"
service = "your-service-name"
CMD = ["/usr/bin/systemctl", action, f"{service}.service"]
result = subprocess.run(CMD, capture_output=True, text=True)
# Log output to file for debugging
with open("data/cron.txt", "a") as f:
    f.write(f"[{action}] {result.returncode} stdout:{result.stdout} stderr:{result.stderr}\n")
```

### Cron entries (example for your service)

```
14 9 * * 1-5 /usr/bin/python3 /path/to/your/project/factory/cron.py start >> /path/to/your/project/data/cron.txt 2>&1
31 15 * * 1-5 /usr/bin/python3 /path/to/your/project/factory/cron.py stop >> /path/to/your/project/data/cron.txt 2>&1
```

- Start: 9:14 AM weekdays
- Stop: 3:31 PM weekdays
