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

## Bug Fixes & Discoveries

### TickRunner Not Detecting Entry Order Completion (2026-04-21)

**Symptom**: Stop loss (exit) order was never placed after entry order completed.

**Root Cause**: TickRunner stored `entry_id` only in its instance variable (`self.entry_id`), but when an order was placed via the API endpoint (`/api/trade`), the order ID was saved to `trade.json`. TickRunner never read from `trade.json`, so it never detected when entry orders completed and never placed the exit order.

**Flow**:
1. User clicks BUY → API calls `Helper.one_side(order_details)` → returns order_id
2. API saves to `trade.json`: `{"entry_id": "26042100278879", "symbol": "...", ...}`
3. TickRunner's `self.entry_id` was always "" (empty string)
4. `is_trade()` checks `self.entry_id` which was always empty → never triggered

**Fix** (`src/tickrunner.py`):
- Added `_load_trade_from_file()` method to read from trade.json on init
- Modified `create()` to check for existing trade before clearing
- Save exit_id to trade.json when exit order is placed
- Now TickRunner properly loads pending trades on startup

**Key Insight**: Always sync state between API and background workers via persistent storage (trade.json), not just instance variables.

### TickRunner LTP Lookup Failing for Non-ATM Symbols (2026-04-21)

**Symptom**: Exit order placed successfully, but modify to market when target reached never triggered. LTP was always None.

**Root Cause**: `tokens_nearest` was only containing 1 symbol (ATM closest to premium). When user traded a different symbol (e.g., P24000 when ATM was P23850), the LTP lookup failed because that symbol wasn't in the subscribed tokens list.

**Flow**:
1. Strategy picks ATM symbol closest to premium (e.g., P23850)
2. `tokens_nearest` = {"NFO|72458": "NIFTY28APR26P23850"} (1 token)
3. User trades P24000 (different strike)
4. trade.json saves symbol="NIFTY28APR26P24000"
5. TickRunner's `self.ltps` only has P23850's LTP
6. `self.ltps.get("P24000")` returns None → modify never triggers

**Fix** (`src/main.py`):
- Pass all 198 subscribed tokens to TickRunner, not just the ATM
- Changed: `runner = TickRunner(ws, tokens_nearest)`
- To: `runner = TickRunner(ws, all_tokens_map)` where all_tokens_map contains all option tokens

**Key Insight**: WebSocket subscribes to many symbols, but we only stored one in tokens_nearest. Need to store ALL subscribed tokens for LTP lookup.

### Cron Start Not Logging (2026-04-21)

**Issue**: Morning cron at 9:14 AM did not write to cron.txt. Service was running (manually started), so cron may have failed silently.

**Current Status**: Investigating why morning cron output is missing from cron.txt.
