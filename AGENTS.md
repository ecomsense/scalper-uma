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

## Lessons Learned (2026-04-24)

### Root Cause: Broker Session Not Initialized on API Calls

**Symptom**: 
- API `/api/summary` returned empty data (`orders:[]`, `positions:[{}]`)
- Position/Order modals showed no data
- All positions showed quantity 0 even when broker had open positions

**Investigation Steps**:
1. Verified broker login was working (logs showed "api connected")
2. Verified only ONE uvicorn process running
3. Tested API directly on server - same empty response
4. Manually called `Helper.api()` before `Helper.summary()` - it worked!

**Root Cause**: 
The broker session (singleton) was created during `trading_session_start()` which runs in the lifespan. However:
- Trading session was stopping immediately after starting (double "started"/"stopped" in logs)
- When trading session stopped, the session wasn't invalidated - `Helper._api` still existed
- BUT something about the session state was broken after stop/start cycles

**The Fix** (`src/main.py`):
```python
@app.get("/api/summary")
async def get_summary(request: Request) -> JSONResponse:
    try:
        api = Helper.api()  # Always call this FIRST to ensure session is valid
        content = Helper.summary()
        return JSONResponse(content)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
```

**Key Lesson**: Never assume the broker session is valid - always call `Helper.api()` before making API calls.

### Related Bug: Multiple Uvicorn Processes

**Symptom**: Trading session starts then immediately stops, even within market hours.

**Root Cause**: Multiple uvicorn processes were running simultaneously:
- One from `systemctl --user start`
- Another from `nohup python -m uvicorn ...` or old process

This caused race conditions where:
1. Process A starts trading session
2. Process B also starts trading session
3. Process A sees process B started, thinks "already running" 
4. Then stops itself

**Prevention**: 
- Use ONE method to start the server (either systemctl OR nohup, never both)
- Always kill all processes before restart: `fuser -k 8000/tcp` or `pkill -f uvicorn`

### Trading Hours Bug (String vs Proper Time Comparison)

**Symptom**: `within_trading_hours` showed `false` even when it was 22:49 IST (within 9:15-23:59).

**Root Cause**: String comparison doesn't work for time:
- Code used: `"9:14" <= hhmm <= "23:59"` (no leading zero on hour)
- String comparison compares character by character:
  - First char: `'9'` (ASCII 57) > `'2'` (ASCII 50) → **FAILS immediately!**
  - This is why `within_trading_hours` was always `false`

**Example**:
```python
hhmm = "22:49"
print("9:14" <= hhmm)  # False! Because '9' > '2'
print("09:14" <= hhmm)  # True! Because '0' < '2'
```

**Fix**: Use proper integer time comparison:
```python
hour = now_ist.hour
minute = now_ist.minute
within_trading_hours = (hour > 9 or (hour == 9 and minute >= 15)) and hour < 23 or (hour == 23 and minute < 59)
```

Where schedule 9:15-23:59 is hardcoded by developer:
- Start: 9:15 `(hour > 9 or (hour == 9 and minute >= 15))`
- End: 23:59 `(hour < 23 or (hour == 23 and minute < 59))`

### Schedule Check on Startup

**Symptom**: App starts trading session even when outside market hours.

**Root Cause**: Lifespan always calls `trading_session_start()` without checking schedule.

**Fix**: Check schedule in lifespan before starting:
```python
async def lifespan(app: FastAPI):
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    minute = now_ist.minute
    day = now_ist.strftime("%a")
    
    in_hours = (hour > 9 or (hour == 9 and minute >= 15)) and hour < 23 or (hour == 23 and minute < 59)
    is_trading_day = day in ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    if in_hours and is_trading_day:
        await trading_session_start(app)
    else:
        logging.info("Outside schedule, skipping...")
    yield
    await trading_session_stop(app)
```

### Frontend Modals Not Showing Data

**Symptom**: Clicking "Details" for Positions/Orders showed empty modals.

**Root Cause**: Two issues:
1. Modal showed BEFORE fetch completed (sync fetch, not async)
2. Browser cache - no auto-fetch on page load

**Fix** (`src/static/summary.js`):
```javascript
// Make modal fetch async and wait for data
async function showPositionsModal() {
    let data = null;
    let cached = localStorage.getItem("summary_cache");
    if (cached) {
        try { data = JSON.parse(cached); } catch (e) {}
    }
    if (!data) {
        // Fetch and WAIT for it
        await new Promise(function(resolve) {
            fetch("/api/summary")
                .then(r => r.json())
                .then(function(d) {
                    localStorage.setItem("summary_cache", JSON.stringify(d));
                    data = d;
                    resolve();
                })
                .catch(function(e) { console.error(e); resolve(); });
        });
        if (!data) return;
    }
    // Now show modal with data...
}

// Auto-fetch on page load
window.addEventListener("DOMContentLoaded", function() {
    doFetch();
});
```

### Candlestick Chart Disabled

**Symptom**: Chart was not appearing, causing browser to hang or show no data.

**Root Cause**: The Lightweight Charts CDN and chart.js were commented out in `index.html`.

**Fix**: Uncomment both:
```html
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.development.js"></script>
```
and:
```html
<script src="/static/chart.js?v=58"></script>
```

## Key Takeaways

1. **Always call `Helper.api()` before broker API calls** - Don't assume session is valid
2. **Never run multiple uvicorn processes** - Causes race conditions
3. **Use ONE method to start server** - Either systemctl OR nohup, never both
4. **Schedule is hardcoded (9:15-23:59)** - Not external config
5. **Modal fetch must be async** - Wait for data before showing modal
6. **Auto-fetch on page load** - Otherwise panel shows stale/empty data
7. **Always use proper time comparison** - Never string comparison for time
8. **Check schedule on startup** - Use lifespan to conditionally start/stop trading