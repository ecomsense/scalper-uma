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
- **Symptom**: Orders modal shows date (e.g., "2026-04-30") instead of time (e.g., "10:30:45")
- **Root Cause**: 
  1. JavaScript tried to extract time with string split, but broker timestamp format varies
  2. toLocaleTimeString still included date in some locales
- **Fix**: 
  1. Use JavaScript `Date()` to parse timestamp
  2. Extract time components manually: getHours(), getMinutes(), getSeconds() with padding
  3. Format as HH:MM:SS without date
- **Code**: `src/static/summary.js:99-108` (manual time extraction)
- **pre**: check_server_responding.sh
- **post**: verify_orders_time_display.sh

### MA Chart Shows Horizontal Price Lines
- **Symptom**: Moving averages displayed unwanted horizontal lines on the right side of the chart, obstructing candlestick view
- **Root Cause**: Line series in LightweightCharts shows price line by default
- **Fix**: Added `priceLineVisible: false` to MA line series configuration in chart.js
- **Code**: `src/static/chart.js:170-175` (line series config)

### App Hangs After Restart Button Click
- **Symptom**: After clicking restart button, app becomes unresponsive (API calls timeout). Sleep page stuck.
- **Root Cause**: Unknown - similar issue seen before. Trading session stop doesn't complete cleanly
- **Workaround**: Service auto-restarts or sleep page auto-starts after ~30s
- **Status**: Needs investigation
