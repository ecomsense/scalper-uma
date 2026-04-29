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
ps aux | grep uvicorn | grep -v grep

# Restart - NEVER use systemctl
pkill -9 -f uvicorn; sleep 2
cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 >> data/log.txt 2>&1 &

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

### Cancel Button Not Working
- **Symptom**: Click does nothing
- **Root Cause**: Status check used lowercase `"trigger_pending"` but broker API returns uppercase `"TRIGGER_PENDING"`
- **Fix**: Use `if status in ['OPEN', 'TRIGGER_PENDING', 'PENDING']`

### order_cancel() Gets Unexpected Keyword Argument
- **Symptom**: `Flattrade.order_cancel() got an unexpected keyword argument 'quantity'`
- **Root Cause**: Broker API `order_cancel()` only accepts `order_id`, not `quantity`
- **Fix**: `cls.api().order_cancel(order_id=o.get('order_id'))` (no quantity kwarg)

### Sell Endpoint 500 Error
- **Symptom**: `/api/trade/sell` returns 500
- **Root Cause**: `ltp` variable was undefined - need to pass as query parameter from frontend

### Logs Button Empty Modal
- **Symptom**: Logs modal shows nothing
- **Root Cause**: Two issues:
  1. fetch used `.text()` but API returns JSON → use `.json()`
  2. `loadLogs()` function was missing from index.html → add it

### Position/Order Modals Show Stale Data
- **Symptom**: Data doesn't update on refresh
- **Root Cause**: Modal used cached data instead of fetching fresh
- **Fix**: Always fetch fresh when opening modal

### JavaScript Not Executing (Sleeping Page)
- **Symptom**: Clock not updating, emojis not showing
- **Root Cause**: `</script>` placed too early in main.py HTML string - code after it becomes plain text

### Log File Not Writing
- **Symptom**: Logs in stdout but not in `data/log.txt`
- **Root Cause**: `settings.yml` `log.show: false` → console only
- **Fix**: Set `log.show: true`

### Historical/Premium Logging Spam
- **Symptom**: Too many INFO logs (every tick)
- **Fix**: Use `logging.debug()` for entries that fire frequently

### Multiple Uvicorn Processes
- **Symptom**: Code changes not taking effect, race conditions
- **Root Cause**: Systemd user service spawning multiple processes
- **Fix**: DO NOT use systemctl - start manually:
```bash
pkill -9 -f uvicorn; sleep 2
cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 >> data/log.txt 2>&1 &
```

### SSE Candlesticks Not Streaming
- **Symptom**: SSE endpoint returns no data for options charts
- **Root Cause**: `tokens_nearest` is a dict `{ws_token: trading_symbol}`. SSE lookup was checking if symbol in dict keys (`if symbol in token_symbols`), but chart passes trading_symbol (dict value), not the ws_token key.
- **Fix**: Check `if symbol in token_symbols.values()` instead of `if symbol in token_symbols`
- **Location**: `src/main.py:560`
- **pre**: scripts/test_sse_endpoint.sh
- **commit**: dd3e57d
- **post**: scripts/verify_sse_stream.sh

**Root Cause (2026-04-28):**
1. `Wserver.ltp` and `Wserver.order_updates` were **class variables** (shared across instances)
   - When a new Wserver was created, the old ltp data remained
   - SSE endpoints read stale data from the class
2. `trading_session_stop()` did not clear state properly

**Fix:**
- Moved `ltp` and `order_updates` to instance variables in `__init__`
- `trading_session_stop()` now calls `_logic_state.reset()` for complete cleanup

**Lesson:** Always use instance variables for per-instance state!

## Troubleshooting Guide

### Service Not Starting
1. Check: `ps aux | grep uvicorn`
2. If port in use: `pkill -9 -f uvicorn; sleep 2 && cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 >> data/log.txt 2>&1 &`
3. Verify: Memory ~80MB, Tasks 10+

### API Returning Empty Data
1. Check: `tail -50 /home/uma/no_env/uma_scalper/data/log.txt`
2. Verify new code: restart with above command
3. Force fresh session: Helper._api = None before calling Helper.api()

### Charts Not Displaying
1. Check SSE: `curl -s http://127.0.0.1:8000/sse/candlesticks/SYMBOL`
2. If historical empty, chart.js now uses live SSE data
3. If SSE returns nothing, check that logic is running (`/api/logic/status` shows `running: true`)

### Bottom Panel Not Updating
1. Check: summary.js has auto-fetch enabled
2. Refresh interval: 5 seconds

### General Debug
1. Always check: `ps aux | grep uvicorn` - should show ONE process
2. Always check: `tail -50 data/log.txt`
3. Kill ghost: `pkill -9 -f uvicorn`

## Best Practices

### Recommended Log Level
**`level: 20` (INFO)** in settings.yml - filters spam (`Using existing session` every 500ms) while keeping important events (session start/stop, entry CANCELED, trade checks, errors).

### Always Use Instance Variables
For FastAPI state (Wserver, Helper, etc.): use instance variables `self.xxx`, not class variables `Wserver.xxx`. Class variables are shared across all instances!

### Key Debug Commands
```bash
ps aux | grep uvicorn | grep -v grep     # Check ONE process
tail -20 /home/uma/no_env/uma_scalper/data/log.txt
grep -i cancel /home/uma/no_env/uma_scalper/data/log.txt | tail -5
curl -s http://127.0.0.1:8000/api/trade/sell?symbol=NIFTY28APR26P24000&ltp=5
curl -s http://127.0.0.1:8000/api/admin/logs | head -c 500
```

## Issue Workflow

1. **Check**: Search AGENTS.md and git history for existing issue
2. **If exists**:
   - Could be regression from another fix - trace what changed with git log
   - Fix not fully documented - add to AGENTS.md
3. **If new**: User opens GitHub issue, I reference issue # in commits
4. **Shell commands**: Create in `scripts/` directory first (not in git), reference in AGENTS.md
5. **Code changes**: Commit with `fix/feat #<issue>` message

### Troubleshooting Format (in AGENTS.md)
For each documented issue:
```
- issue: <description>
  pre: <scripts/check_issue.sh>
  commit: <git hash of fix>
  post: <scripts/verify_fix.sh>
```

Example:
```
- SSE candlesticks not streaming
  pre: scripts/test_sse_endpoint.sh
  commit: dd3e57d
  post: scripts/verify_sse_stream.sh
```

## Scripts Directory

Store server/system commands in `scripts/` for reproducibility:
- Restart commands
- Log inspection
- Process management

