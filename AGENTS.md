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

