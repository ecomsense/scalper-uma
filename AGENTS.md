# Scalper-UMA Agent Context

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 CONTROLLER (main.py)                        │
│  - APScheduler for auto start/stop within schedule          │
│  - PID lock to prevent multiple instances                   │
│  - HTTP Basic Auth                                          │
│  - Serves sleeping.html or logic.html based on schedule     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LOGIC APP                                   │
│  - Trading session (TickRunner, Strategy, Wserver)          │
│  - State stored in src/state.py (LogicState)                │
│  - Start/Stop/Pause via /api/logic/* endpoints              │
└─────────────────────────────────────────────────────────────┘
```

## Schedule (hardcoded in ScheduleConfig class)

| Setting | Value |
|---------|-------|
| Start | 09:15 IST |
| End | 15:31 IST |
| Days | Mon-Fri |

## Session Management (Helper.api)

- Session TTL: 7 hours (auto-expire before broker token rotation)
- Logs: `Session expired (age: X.Xh), reconnecting...` when reconnecting
- Manual reset: `Helper.reset()` for explicit session reset

## UI Structure

### Header (shared)
```html
<div class='app-header'>
  <div class='header-title'>
    <span>📈</span>
    <span>UMA Scalper</span>
  </div>
  <div class='header-actions'>
    <button class='icon-btn'>🔄</button>
    <button class='icon-btn'>📋</button>
    <button class='icon-btn'>⚙️</button>
  </div>
</div>
```

### Bottom Panel (logic page only)
```html
<div class='bottom-panel'>
  <div class='panel-item'>Positions: <a href='#'><span>0</span></a></div>
  <div class='panel-item'>Orders: <a href='#'><span>0</span></a></div>
  <div class='panel-item'>M2M: <span>0.00</span></div>
  <div class='panel-item'>Realized: <span>0.00</span></div>
</div>
```

### Footer (shared)
```html
<footer class='app-footer'>
  Made with <span class='heart'>❤</span> by <a href='https://ecomsense.in'>ecomsense.in</a>
</footer>
```

## CSS Classes

| Class | Purpose |
|-------|---------|
| `.app-header` | Header bar with flex space-between |
| `.header-title` | Left side: icon + title |
| `.header-actions` | Right side: icon buttons |
| `.icon-btn` | Action buttons (🔄📋⚙️) |
| `.chart-grid` | Flex container for charts |
| `.chart-container` | Individual chart box |
| `.bottom-panel` | Summary bar: Positions/Orders/M2M/Realized |
| `.panel-item` | Individual metric with color-coded values |
| `.app-footer` | Sticky footer with branding |
| `.schedule-info` | Schedule display on sleeping page |
| `.sleep-container` | Center content on sleeping page |
| `.modal` / `.modal-content` | Modal overlays |

## Route Structure

| Path | Description |
|------|-------------|
| `/` | Root - sleeping or logic page based on schedule |
| `/api/schedule` | Schedule info, within_schedule, times |
| `/api/logic/start` | Start trading session |
| `/api/logic/stop` | Stop trading session |
| `/api/logic/status` | Running, paused, pause_reason |
| `/api/summary` | Positions, orders, m2m, realized_pnl |
| `/api/admin/logs` | Server log content |
| `/api/admin/settings` | Read/write settings.yml |
| `/api/chart/settings` | MA configuration for charts |

## Server

**IP**: 65.20.83.178 | **User**: uma

### Commands
```bash
# Check status
systemctl --user status fastapi_app.service

# Restart (ONLY use systemctl - NEVER start uvicorn directly)
systemctl --user restart fastapi_app.service

# Logs
tail -50 /home/uma/no_env/uma_scalper/data/log.txt

# Check API
curl -s http://127.0.0.1:8000/api/schedule
curl -s http://127.0.0.1:8000/api/logic/status
```

## Responsive Design

- **< 900px**: Charts stack vertically, no gap between them
- **> 900px**: Charts side by side with gap

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
| `src/static/styles.css` | Shared CSS for both pages |
| `src/static/summary.js` | Bottom panel updates |
| `templates/sleeping.html` | Countdown page |
| `templates/logic.html` | Trading charts + bottom panel |

## Recent Bug Fix

- `src/main.py:560` - SSE candlesticks: the lookup was checking if symbol in dict keys instead of values. `tokens_nearest` is a dict `{ws_token: trading_symbol}`, and chart passes trading_symbol (value), not key. Now checks `symbol in token_symbols.values()`.

## Milestones

- `milestone/sse-fix` - SSE candlesticks: check symbol in dict values not keys
- `milestone/migration-complete` - Latest: session TTL, schedule 09:15, UI fixed
- `milestone/ui-fully-complete` - Responsive layouts, bottom panel
- `milestone/app-footer-fixed` - Consolidated CSS, shared components
## Known Issues & Fixes (Do Not Repeat)

### SSE Candlesticks Stopped After Restart
**Root Cause (2026-04-28):**
1. `Wserver.ltp` and `Wserver.order_updates` were **class variables** (shared across instances)
   - When a new Wserver was created, the old ltp data remained in the class variable
   - SSE endpoints read stale data from the class, not the current instance
2. `trading_session_stop()` did not clear state properly - left `tokens_nearest` and other fields populated

**Fix Applied:**
- Moved `ltp` and `order_updates` to instance variables in `__init__`
- `trading_session_stop()` now calls `_logic_state.reset()` for complete cleanup

**Lesson:** Always use instance variables for per-instance state. Class variables are shared!

### Multiple Processes Spawning
**Root Cause:** The watchdog scheduler was running every 60 seconds and restarting sessions, while the PID lock was working correctly but creating new processes that immediately exited.

**Lesson:** Ensure `is_running()` check is solid before starting new sessions.


### PID Lock False Positive - Another instance for Same PID
- **Symptom**: Another instance is running (PID: X) errors every 6 seconds even though only one process running
- **Root Cause**: check_pid_lock() didnt check if old_pid == os.getpid() before os.kill()
- **Fix**: Added if old_pid == os.getpid(): return True before os.kill in check_pid_lock()
- **pre**: check_server_responding.sh
- **post**: verify_settings_reload.sh

### Server Crashing with Another instance errors
- **Symptom**: Service stuck in restart loop, Another instance is running errors every 6 seconds
- **Root Cause**: Multiple issues - PID lock false positive, port 8000 occupied, user service cant specify User/Group
- **Fix**: Set SKIP_PID_LOCK=1 in service Environment, use Restart=always
- **pre**: check_server_responding.sh
- **post**: verify_settings_reload.sh

### Unclean Restart - Ghost Websocket References in SSE Streams
- **Symptom**: Restart button calls stop/start but old websocket held in memory by SSE loops, broker login tangled
- **Root Cause**: 
  1. on_start() and on_stop() lifecycle hooks defined but never invoked
  2. SSE endpoints cached ws outside while loop - old ws never garbage collected
  3. Websocket TCP connection never explicitly closed on stop
- **Fix**:
  1. Added on_start() call after state initialized in trading_session_start()
  2. Added on_stop() call before reset in trading_session_stop()
  3. Added ws.close() in trading_session_stop() to close broker connection
  4. SSE endpoints check if not _logic_state.is_running() to break and disconnect
  5. Added 2s delay in restart endpoint + Helper.reset() for fresh broker login
- **pre**: check_server_responding.sh
- **post**: verify_settings_reload.sh

### Restart Button Not Redirecting to Sleep Page
- **Symptom**: Restart button hangs or doesn't redirect properly
- **Root Cause**: Complex restart logic with multiple awaits, used reload() which reloads logic page not sleep page
- **Fix**: Simplified restartLogic to only stop_logic() + redirect to /. Let scheduler handle startup based on market hours
- **pre**: check_server_responding.sh
- **post**: verify_settings_reload.sh

### Sleep Page Doesn't Auto-Start After Restart (During Market Hours)
- **Symptom**: After restart button redirects to /, sleep page stays stuck showing countdown. Trading doesn't resume
- **Root Cause**: `/logic` route checks `if within_schedule AND running` before serving logic.html. Sleep page only redirected if `logicData.running=true`. After restart, running=false, so no redirect
- **Fix**: Sleep page now checks if `within_schedule && !running`, auto-calls POST `/api/logic/start`, waits 1s, then redirects to `/logic`
- **pre**: check_restart_during_hours.sh
- **post**: verify_auto_restart_resume.sh

### Settings Save Doesn't Clear Session State
- **Symptom**: After saving settings and restarting, old broker session and startup_data persist, causing login confusion
- **Root Cause**: 
  1. `saveAndRestart()` saved settings and called `restartLogic()`, but didn't call `Helper.reset()` to clear session state
  2. Missing 2s delay between reset and stop caused old session to linger during stop transition
- **Fix**: 
  1. Created new endpoint `/api/admin/reset` that calls `Helper.reset()`
  2. Modified `saveAndRestart()` to: save settings → reset → **wait 2s** → stop → redirect to /
  3. Sleep page auto-start handles restart during market hours
- **pre**: check_settings_reload.sh
- **post**: verify_settings_reset_flow.sh

### MA Color Support
- **Symptom**: Users found it difficult to identify MAs on charts when colors were random
- **Solution**: Added optional `color` field to MA config in settings.yml
- **Implementation**:
  1. Added colorMap with 20+ English color names (red, green, blue, purple, orange, teal, etc.)
  2. Chart.js checks if MA has user-defined color, falls back to random palette if color unknown
  3. Example config:
     ```yaml
     ma:
       - type: ema
         period: 10
         price: low
         color: red
       - type: ema
         period: 20
         price: close
         color: green
     ```
- **Code**: `src/static/chart.js:42-99` (colorMap, getColorHex, getRandomColor functions)

### Systemd Logging to data/log.txt
- **Symptom**: FastAPI/Uvicorn logs were only in journalctl, not in application log file
- **Solution**: Configure systemd to append stdout/stderr to data/log.txt
- **Implementation**:
  1. Updated factory/uma-scalper.service with StandardOutput/StandardError directives
  2. Applied same changes to server's /home/uma/.config/systemd/user/fastapi_app.service
  3. Systemd daemon-reload and restart service
- **Result**: All logs (FastAPI startup, application logs, system events) now in single file: data/log.txt
- **Code**: `factory/uma-scalper.service` (service template), `src/main.py` (logging config)

### Orders Timestamp Shows Date Instead of Time
- **Symptom**: Orders modal shows date (e.g., "30-04-2026") or "11:36:34 30-04-2026" instead of just time (e.g., "11:36:34")
- **Root Cause**: Broker sends timestamp in format "HH:MM:SS DD-MM-YYYY" - JavaScript Date() can't parse this
- **Fix**: Split by space and take first part (HH:MM:SS) - broker already sends time in correct format
- **Code**: `src/static/summary.js:99-108` (split by space, extract time)
- **pre**: check_server_responding.sh
- **post**: verify_orders_time_display.sh

### MA Chart Shows Horizontal Price Lines
- **Symptom**: Moving averages displayed unwanted horizontal lines on the right side of the chart, obstructing candlestick view
- **Root Cause**: Line series in LightweightCharts shows price line by default
- **Fix**: Added `priceLineVisible: false` to MA line series configuration in chart.js
- **Code**: `src/static/chart.js:170-175` (line series config)

### App Hangs After Restart Button Click
- **Symptom**: After clicking restart button, app becomes unresponsive (API calls timeout). Sleep page stuck.
- **Root Cause**: Trading session stop doesn't complete cleanly. SSE streams may not be cleaning up properly, or stale broker session causes blocking calls
- **Learning from power-option**:
  1. Power-option uses direct WebSocket instead of SSE (simpler architecture)
  2. Power-option deletes token on startup to force fresh login
  3. Power-option has simpler trading_session_stop
- **Fix Applied**:
  1. Call Helper.reset() in lifespan startup to force fresh broker login
  2. Add asyncio.wait_for with 2s timeout for stopping operations
  3. Call Helper.reset() after stopping to clear broker session
- **How it works now**:
  - **Restart button click**:
    1. Frontend calls POST `/api/logic/stop`
    2. Backend calls `trading_session_stop()`:
       - Calls `on_stop()` lifecycle hook
       - Cancels TickRunner task (with 2s timeout via asyncio.wait_for)
       - Closes websocket via `_logic_state.ws.close()`
       - Calls `_logic_state.reset()` and `Helper.reset()` to clear broker session
    3. Frontend redirects to `/` (sleep page)
  - **Next startup** (sleep page auto-start or manual):
    1. `lifespan()` calls `Helper.reset()` on startup (forces fresh broker login)
    2. Creates fresh websocket connection
    3. Trading starts
- **Log indicators**:
  - `Session reset on startup - forcing fresh broker login` (at startup)
  - `Broker session reset` (after stop)
  - `Closing broker websocket...` (before stop completes)
- **pre**: scripts/check_restart_button.sh
- **post**: scripts/verify_restart_button.sh

### Systemd Service Restart Loop at Midnight
- **Symptom**: Service killed and stuck in restart loop around midnight every day. Systemd shows "Failed with result 'exit-code'" repeatedly.
- **Root Cause**: Extra `ExecStartPre=/usr/bin/sleep 1` in server's service file caused systemd to think service was failing. Also had incorrect path for fuser command.
- **Fix Applied**:
  1. Removed unnecessary sleep from ExecStartPre
  2. Used correct command: `/bin/sh -c 'fuser -k 8000/tcp || true'`
  3. Set RestartSec=5 (was 30)
- **Server Command**:
  ```bash
  cat > ~/.config/systemd/user/fastapi_app.service << 'EOF'
  [Unit]
  Description=UMA Scalper - Options Trading Bot
  After=network.target

  [Service]
  Type=simple
  WorkingDirectory=/home/uma/no_env/uma_scalper
  Environment="PATH=/home/uma/no_env/uma_scalper/.venv/bin"
  Environment=SKIP_PID_LOCK=1
  ExecStartPre=/bin/sh -c 'fuser -k 8000/tcp || true'
  ExecStart=/home/uma/no_env/uma_scalper/.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
  StandardOutput=append:/home/uma/no_env/uma_scalper/data/log.txt
  StandardError=append:/home/uma/no_env/uma_scalper/data/log.txt
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=default.target
  EOF
  systemctl --user daemon-reload
  ```

### Port Binding Error on Restart
- **Symptom**: `[Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use` + "fuser: not found" in logs
- **Root Cause**: systemd user service uses minimal PATH, fuser not found. Old processes not killed properly, systemd restart too fast.
- **Fix**:
  1. Use absolute path: `/usr/bin/fuser -k -9 8000/tcp` (SIGKILL ensures stuck processes die)
  2. Add settling delay: `/usr/bin/sleep 1` to allow kernel to release port
  3. Updated factory/uma-scalper.service with hardened ExecStartPre
- **Command**: `/usr/bin/fuser -k -9 8000/tcp && sleep 1 && systemctl --user daemon-reload && systemctl --user restart fastapi_app.service`
- **Files**: factory/uma-scalper.service

### Systemd User Service Group Permission Error
- **Symptom**: `Failed to determine supplementary groups: Operation not permitted` and `Failed at step GROUP spawning /bin/sh: Operation not permitted`
- **Root Cause**: User=uma in service file causes systemd to try to set up supplementary groups, which fails for --user services.
- **Fix**:
  1. Remove `User=uma` line from service file (not needed for --user services)
  2. Use `/usr/bin/sleep` directly instead of shell wrapper
  3. Change `WantedBy=multi-user.target` to `WantedBy=default.target`
- **Files**: factory/uma-scalper.service, ~/.config/systemd/user/fastapi_app.service

### Positions Modal - Add/Square/Cover Actions
- **Feature**: Positions modal now has action buttons based on position type
- **Implementation**:
  - qty > 0: Square button (sell at LTP-2)
  - qty < 0: Cover button (buy at LTP+2)
  - qty == 0: Add button (opens buy modal)
- **Files**: `src/static/summary.js`, `templates/logic.html`, `src/main.py`
- **Add**: Opens modal with symbol, exchange, product from position row

### Buy Order Modal - Product Aware
- **Feature**: Add button passes product type from position row to buy order
- **Display**: Shows NFO:SYMBOL | NRML | LIMIT Order
- **Backend**: /api/position/add accepts product field

### Orders Modal - Cancel Button + Balloonified
- **Feature**: 
  - Cancel (X) button only for OPEN/TRIGGER_PENDING status
  - All columns balloonified based on side (B=green, S=red)
- **CSS**: Consolidated to style.css classes (.cell-buy, .cell-sell, etc.)
- **pre**: check_orders_modal.sh
- **post**: verify_orders_modal.sh

### Settings Not Reloading After App Restart
- **Symptom**: Changed MA settings in settings.yml, restarted app, but new settings don't take effect
- **Root Cause**: `logic_app.get_settings()` imported `O_SETG` directly from constants module. At import time, `O_SETG` is eagerly loaded and cached. Even after `load_env_settings()` is called, the direct import still returns stale cached values.
- **Additional Issue**: `/api/chart/settings` endpoint also used `O_SETG` directly instead of `get_settings()`
- **Fix**:
  1. Changed `logic_app.get_settings()` to call `get_settings()` from constants which returns fresh values
  2. Added 'ma' to returned settings dict so it's available for charts
  3. Changed `/api/chart/settings` to use `get_settings()` from logic_app
- **Code**: `src/logic_app.py:47-52`, `src/main.py:404-413`

### Browser Caching Causes Wrong Page to Load
- **Symptom**: After saving settings in logic page, user redirected to sleep page but sees logic page content (old scripts loading, wrong modals)
- **Root Cause**: Browser caches HTML pages, especially when redirecting after POST requests
- **Fix Applied**:
  1. Added cache-busting version params to all static resources (`?v=2`, `?v=12`, `?v=60`)
  2. Added timestamp to all `window.location.href` redirects (`?t=` + Date.now())
- **Files**: `templates/logic.html`, `templates/sleeping.html`

### Flattrade Websocket Not Closing Properly on Stop
- **Symptom**: After restart, websocket errors "socket is already opened" - broker sees old session still active
- **Root Cause**: Called `ws.close()` which is WebSocketApp's close, not broker's `close_websocket()`. Broker's internal state `__websocket_connected` stays True, so broker keeps old session alive.
- **Fix**: Changed `_logic_state.ws.close()` to `_logic_state.ws.close_websocket()` in `src/logic_app.py:164`
- **Code**: `src/logic_app.py:161-166`
