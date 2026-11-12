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
| End | 21:30 IST |
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

**Access**: SSH via alias `uma` (see `~/.ssh/config` - never hardcode user/IP here)
**Deploy**: run `scripts/deploy.sh` on the remote server itself (pulls, `uv sync --frozen`, restarts)
**Project dir**: resolved from the systemd unit - `systemctl --user show fastapi_app.service -p WorkingDirectory --value`

### Commands
```bash
# Check status
systemctl --user status fastapi_app.service

# Restart (ONLY use systemctl - NEVER start uvicorn directly)
systemctl --user restart fastapi_app.service

# Logs
tail -50 data/log.txt   # from the app dir

# Check API
curl -s http://127.0.0.1:8000/api/schedule
curl -s http://127.0.0.1:8000/api/logic/status
```

## Scripted Operations - agents run THESE, never ad-hoc commands

Every recurring operation on the remote is already scripted here. Run scripts, don't improvise commands (this keeps agent actions auditable and prevents arbitrary remote execution).

| Situation | Script |
|-----------|--------|
| Deploy latest code to remote | `scripts/deploy.sh` (run ON the remote) |
| Local fast checks, no network | `scripts/dev-check.sh` |
| Is server responding? (pre-test) | `scripts/check_server_responding.sh` |
| Restart button pre/post test | `scripts/check_restart_button.sh` → test → `scripts/verify_restart_button.sh` |
| Restart during market hours | `scripts/check_restart_during_hours.sh` → test → `scripts/verify_auto_restart_resume.sh` |
| Settings reload pre/post | `scripts/check_settings_reload.sh` → test → `scripts/verify_settings_reload.sh` / `scripts/verify_settings_reset_flow.sh` |
| SSE candlesticks | `scripts/test_sse_endpoint.sh` / `scripts/verify_sse_stream.sh` |
| Websocket close pre/post | `scripts/check_websocket_close.sh` → test → `scripts/verify_websocket_close.sh` |
| Port binding issue | `scripts/fix-port-binding.sh` |

Rule: if a check isn't scripted yet, write a `scripts/check_*.sh` (pre) or `scripts/verify_*.sh` (post) instead of running bare commands. Record it in this table.

## Responsive Design

- **< 900px**: Charts stack vertically, no gap between them
- **> 900px**: Charts side by side with gap

## Known Issues (Do Not Repeat) - one line per lesson; verification lives in scripts/

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| SSE candles stop after restart | `Wserver.ltp`/`order_updates` were class vars (stale across instances); stop left state populated | instance vars in `__init__`; `trading_session_stop()` calls `_logic_state.reset()` |
| Multiple processes spawning | watchdog restarted sessions every 60s while PID lock spawned/exited new ones | solid `is_running()` check before starting sessions |
| PID lock false positive (own PID) | `check_pid_lock()` killed its own PID | `if old_pid == os.getpid(): return` before `os.kill` |
| Restart loop, "Another instance" errors | PID false positive + port occupied + `User=` in a user service | `SKIP_PID_LOCK=1`, `Restart=always`, `ExecStartPre fuser -k -9` |
| Ghost websocket in SSE streams | lifecycle hooks never invoked; ws cached outside SSE loop; TCP never closed | call `on_start()`/`on_stop()`, break SSE when not running, close broker ws on stop |
| Restart button hangs | complex restart with `reload()` | stop only + redirect to `/`, scheduler handles resume |
| Sleep page stuck after restart | `/logic` route requires `running`; nothing auto-started | sleep page auto-starts when `within_schedule && !running` |
| Stale session after settings save | `saveAndRestart()` never called `Helper.reset()` | `/api/admin/reset` + 2s delay; sleep page auto-start covers restarts |
| App hangs after restart click | blocking broker calls; SSE/websocket not cleaned on stop | `Helper.reset()` in lifespan, `asyncio.wait_for` 2s on stop, explicit close |
| Midnight systemd restart loop | stray `ExecStartPre` sleep read as failure; wrong fuser path | remove sleep, absolute `/usr/bin/fuser`, `RestartSec=5` |
| Port binding error on restart | fuser not in systemd PATH; restart faster than kernel | absolute `/usr/bin/fuser -k -9` + `sleep 1` |
| GROUP permission error (user service) | `User=` line in `--user` service | drop `User=`, `WantedBy=default.target` |
| Settings not reloading after restart | direct import of eagerly-cached `O_SETG` | fresh `get_settings()` accessor everywhere |
| Orders timestamp shows date | broker sends "HH:MM:SS DD-MM-YYYY", `Date()` chokes | `split(" ")[0]` in `summary.js` |
| MA chart shows horizontal price lines | LightweightCharts shows price lines by default | `priceLineVisible: false` on MA series |
| MA colors not identifiable | random palette | optional `color` field in settings MA config |
| Browser caches wrong page after save | cached HTML after POST redirects | cache-busting `?v=` on statics, `?t=` on redirects |
| Flattrade ws "already opened" on restart | `ws.close()` ≠ broker `close_websocket()`; broker keeps session | call broker's `close_websocket()` |

## Feature Log (one line each)

- Positions modal: Square (qty>0, LTP−2) / Cover (qty<0, LTP+2) / Add (qty=0) actions
- Buy order modal: product-aware (symbol | exchange | product shown)
- Orders modal: cancel (X) only for OPEN/TRIGGER_PENDING; balloonified by side
