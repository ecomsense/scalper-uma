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

### Important: Do NOT use systemctl!

Systemd spawns multiple uvicorn processes causing race conditions and stale data.

### Starting/Stopping Server (Manual)
```bash
# Kill any existing process first
ssh uma@65.20.83.178 "fuser -k 8000/tcp"

# Start manually
ssh uma@65.20.83.178 "cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &"
```

### Restarting After Code Changes
```bash
# Local: commit and push
cd /home/pannet1/py/fastapi/scalper-uma && git add -A && git commit -m "message" && git push

# Server: pull, kill port, start fresh
ssh uma@65.20.83.178 "cd /home/uma/no_env/uma_scalper && git pull && fuser -k 8000/tcp && sleep 2 && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &"
```

### Always Check for Ghost Processes
```bash
ssh uma@65.20.83.178 "ps aux | grep uvicorn"
```
Should show only ONE process.

### Testing Endpoints
```bash
ssh uma@65.20.83.178 "curl -s http://127.0.0.1:8000/api/chart/settings"
```

### Killing Ghost Processes
If multiple uvicorn processes are running:
```bash
ssh uma@65.20.83.178 "pkill -9 -f 'uvicorn.*8000' && sleep 2 && cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &"
```

## Common Tasks

- **Add API endpoint**: Add to `src/main.py` with `@app.post/get`
- **Modify trading logic**: Edit `src/strategy.py`
- **Change broker**: Update `broker` in credentials yml

## Important Notes

- The "session" in this codebase refers to the broker API connection (Finvasia)
- No database - uses JSON files for persistence
- Trades NIFTY/BANKNIFTY options based on premium proximity
- Start uvicorn manually (see Server Management section below)
- Delete cached bytecode: `rm -rf src/__pycache__`

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
pkill -9 -f 'uvicorn.*8000' && sleep 2 && cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &
```

## Troubleshooting

### Summary Shows 0 Orders

**Symptom**: `/api/summary` returns 0 orders.

**Root Cause**: Multiple uvicorn processes running (each with its own singleton).

**Fix**: Single process, singleton reused. Read code to trace order flow, don't check broker API.

### How to Trace Order Flow (Without Broker API)

1. **Frontend buttons** in `src/static/chart.js`:
   - `High` button → sends `order_type: "SL"` (Stop-Limit)
   - `MKT` button → sends `order_type: "LMT"` (Limit)
   
   | Button | order_type | price |
   |--------|------------|-------|
   | **High** | `"SL"` | prev.high + 0.05 |
   | **MKT** | `"LMT"` | curr.close + 2 |

2. **Backend endpoint** in `src/main.py:521`:
   - `@app.post("/api/trade/buy")` receives payload
   - Calls `Helper.one_side(order_details)` to place order

3. **Helper class** in `src/api.py`:
   - `one_side()` → calls `cls.api().order_place(**bargs)` → broker API

**Never check broker API to understand order flow** - trace through the code instead.

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
- One from manual start
- Another from previous process or reload

This caused race conditions where:
1. Process A starts trading session
2. Process B also starts trading session
3. Process A sees process B started, thinks "already running" 
4. Then stops itself

**Prevention**: 
- Use ONE method to start the server (manual start only)
- Always kill all processes before restart: `pkill -9 -f 'uvicorn.*8000'`

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

## Dev Tools

### Scripts Location
- `~/Scripts/git_hooks/` - Common scripts for all projects

### Scripts
| Script | Purpose |
|--------|--------|
| `dev-check.sh` | Syntax + lint + tests locally |
| `deploy.sh` | Commit + push + restart server |
| `install-dev.sh` | Setup dev environment |

### Usage
```bash
# Local checks (runs syntax + lint + tests)
dev-check.sh

# Deploy to server
deploy.sh "commit message"
```

### Git Hooks (Auto-run on commit)
Pre-commit hooks run automatically on `git commit`:
- Syntax check (`python -m py_compile`)
- Lint check (`ruff check --fix`)
- Run tests (`pytest`)

**Setup in new project:**
```bash
cp ~/Scripts/git_hooks/.pre-commit-config.yaml /path/to/project/
cd /path/to/project && uv run pre-commit install
```

### Workflow
```bash
# 1. Make code changes
# 2. Test locally (optional)
dev-check.sh

# 3. Commit - hooks run automatically
git add -A
git commit -m "message"

# 4. Deploy to server
deploy.sh "message"
```

### Server Auto-Deploy (Not Set Up)
Server can auto-pull from GitHub using cron/webhook. Left for later investigation.

## Bugs Fixed (2026-04-27)

### Cancel Button Not Working

**Symptom**: Cancel button click does nothing.

**Root Cause**: Order status check used lowercase `"trigger_pending"` but broker API returns uppercase `"TRIGGER_PENDING"`.

**Fix** (`src/api.py`):
```python
# WRONG:
if o.get("status") in ["OPEN", "trigger_pending", "PENDING"]:

# CORRECT:
if o.get("status") in ["OPEN", "TRIGGER_PENDING", "PENDING"]:
```

### Cancel ltp Undefined

**Symptom**: Cancel endpoint returns 500 error.

**Root Cause**: `ltp` variable was undefined in `/api/trade/sell` endpoint.

**Fix**: Accept `ltp` as query parameter from frontend:
```python
@app.get("/api/trade/sell")
async def reset(symbol: str = "", ltp: float = 0) -> JSONResponse:
    Helper.close_all_for_symbol(symbol, ltp)
```

Frontend sends ltp:
```javascript
const ltp = candleData[candleData.length - 1].close;
fetch(`/api/trade/sell?symbol=${symbol}&ltp=${ltp}`)
```

### Logs Button Not Working

**Symptom**: Clicking Logs button shows empty modal.

**Root Cause**: Fetch used `.text()` but API returns JSON.

**Fix**:
```javascript
// WRONG:
fetch('/api/admin/logs').then(r=>r.text()).then(t=>...)

// CORRECT:
fetch('/api/admin/logs').then(r=>r.json()).then(d=>...)
```

### Position/Order Modals Show Stale Data

**Symptom**: Modals show old data even after refresh.

**Root Cause**: Modals used cached data instead of fetching fresh.

**Fix**: Always fetch fresh data when opening modals:
```javascript
async function showPositionsModal() {
    const data = await fetch("/api/summary").then(r => r.json());
    // Display data...
}
```

### Multiple Uvicorn Processes (Again)

**Symptom**: Bottom panel not updating, code changes not taking effect.

**Root Cause**: Systemctl keeps spawning multiple uvicorn processes.

**Fix**: DO NOT use systemctl. Start manually:
```bash
# Kill existing
fuser -k 8000/tcp

# Start manually
cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &
```

**Always check**: `ps aux | grep uvicorn` - should show only ONE process.

## Bugs Fixed (2026-04-27) - Continued

### Cancel Button API Error: order_cancel() got unexpected keyword argument 'quantity'

**Symptom**: Cancel request hits server but order doesn't cancel, error in logs: `Flattrade.order_cancel() got an unexpected keyword argument 'quantity'`

**Root Cause**: Broker API's `order_cancel()` only accepts `order_id`, not `quantity`.

**Fix** (`src/api.py`):
```python
# WRONG:
cancel_args = {
    'order_id': o.get('order_id'),
    'quantity': o.get('quantity'),
}
cls.api().order_cancel(**cancel_args)

# CORRECT:
cls.api().order_cancel(order_id=o.get('order_id'))
```

### JavaScript Code Outside Script Tag (Sleeping Page)

**Symptom**: Clock not updating, emojis not showing, logs not loading on sleeping page.

**Root Cause**: In `src/main.py` HTML string, `</script>` was placed too early, causing all JavaScript after line 406 to be outside the script tag as plain text.

**Fix**: Move `</script>` to the proper location after all JavaScript code:
```python
# Before (broken):
<script>
  fetch('/api/admin/settings').then(...)
</script>
  const emojis = [...];  // This is PLAIN TEXT, not JavaScript!
  function updateClock() {...}
</script>

# After (fixed):
<script>
  fetch('/api/admin/settings').then(...)
  const emojis = [...];
  function updateClock() {...}
</script>
```

### loadLogs() Function Not Defined (Trading Page)

**Symptom**: Logs modal opens but clicking Refresh does nothing. Console shows `loadLogs is not defined`.

**Root Cause**: `loadLogs()` function was missing from `src/static/index.html`. It was referenced but never defined.

**Fix** (`src/static/index.html`):
```javascript
function loadLogs() {
    fetch('/api/admin/logs')
        .then(r => r.json())
        .then(d => document.getElementById('logsEditor').value = d.content)
        .catch(e => console.error('Logs error:', e));
}
```

Also auto-load logs when opening modal:
```javascript
function openLogsModal() {
    document.getElementById('logsModal').style.display = 'block';
    loadLogs();  // Auto-fetch logs on open
}
```

### Log File Not Writing (Logger misconfigured)

**Symptom**: Logs appear in stdout but not in `data/log.txt`.

**Root Cause**: In `data/settings.yml`, `log.show: false` means Logger writes nowhere (console only when show=false, file only when show=true).

**Fix** (`data/settings.yml`):
```yaml
log:
  show: true   # Must be true to write to file
  level: 10    # DEBUG level
```

Also ensure `S_LOG` path in constants.py is correct (absolute path to data/log.txt).

### Recommended Log Level for Production

Based on previous session's problems with session handling and order placements:

**Set `level: 20` (INFO)** in settings.yml

This filters out spam (`Using existing session` every 500ms, per-order lookup logs) while keeping important events:
- `INFO: ✅ Trading session started`
- `INFO: Entry CANCELED: ...`
- `INFO: TRADE CHECK: target=..., exit=..., ltp=...`
- `ERROR: Error cancelling orders`

### Systemd User Service Auto-Restarting Uvicorn

**Symptom**: Multiple uvicorn processes keep spawning even after killing them.

**Root Cause**: A systemd user service was configured and kept auto-restarting uvicorn every ~15 minutes.

**Fix**:
```bash
# Stop and disable the service
systemctl --user stop fastapi_app.service
systemctl --user disable fastapi_app.service

# Remove the service file
rm ~/.config/systemd/user/fastapi_app.service

# Reload systemd
systemctl --user daemon-reload

# Then start manually (never use systemctl for this project)
cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 >> data/log.txt 2>&1 &
```

### Bottom Panel Format: Open Orders / Total Orders

**Change**: Bottom panel now shows `open_orders / total_orders` instead of just `total_orders`.

**Implementation** (`src/static/summary.js`):
```javascript
if (ordEl) ordEl.textContent = activeOrders + ' / ' + orderCount;
```

Where `activeOrders` = orders with status `OPEN`, `TRIGGER_PENDING`, or `PENDING`.

## Key Debugging Commands

```bash
# Check uvicorn processes
ps aux | grep uvicorn | grep -v grep

# Check recent logs
tail -20 /home/uma/no_env/uma_scalper/data/log.txt

# Search for specific log messages
grep -i cancel /home/uma/no_env/uma_scalper/data/log.txt | tail -5

# Test API directly
curl -s http://127.0.0.1:8000/api/trade/sell?symbol=NIFTY28APR26P24000&ltp=5

# Test logs endpoint
curl -s http://127.0.0.1:8000/api/admin/logs | head -c 500
```