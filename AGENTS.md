# Scalper-UMA Agent Context

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 CONTROLLER (main.py)                        │
│  - APScheduler for auto start/stop within schedule             │
│  - PID lock to prevent multiple instances                 │
│  - HTTP Basic Auth                                    │
│  - Serves sleeping.html or logic.html based on schedule       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LOGIC APP                                │
│  - Trading session (TickRunner, Strategy, Wserver)       │
│  - State stored in src/state.py (LogicState)           │
│  - Start/Stop/Pause via /api/logic/* endpoints     │
└─────────────────────────────────────────────────────────────┘
```

## Shared UI Components

### Header Pattern (icon-btn)
Both sleeping.html and logic.html share the same header buttons pattern:

```html
<header class='app-header'>
  <div class='header-left'>
    <span>📈</span>
    <span>UMA Scalper</span>
  </div>
  <div class='header-right'>
    <button class='icon-btn' onclick='restartLogic()' title='Restart'>🔄</button>
    <button class='icon-btn' onclick='openLogsModal()' title='Logs'>📋</button>
    <button class='icon-btn' onclick='openSettingsModal()' title='Settings'>⚙️</button>
  </div>
</header>
```

### Footer Pattern
Both pages share the app-footer:

```html
<footer class='app-footer'>
  Made with <span>❤</span> by <a href='https://ecomsense.in'>ecomsense.in</a>
</footer>
```

### CSS Shared Classes
- `.app-header` - Header styling
- `.app-footer` - Footer styling
- `.icon-btn` - Icon button styling (⚙️ 📋 🔄)
- `.modal` - Modal overlay styling
- `.bottom-panel` - Fixed trading summary panel

## Route Structure

| Path | Description |
|------|------------|
| `/` | Root - shows sleeping or logic page based on schedule |
| `/api/schedule` | Schedule info (start, end, trading days) |
| `/api/logic/start` | Start trading session |
| `/api/logic/stop` | Stop trading session |
| `/api/logic/status` | Trading status |
| `/api/admin/logs` | Server logs |
| `/api/admin/settings` | Edit settings.yml |
| `/api/chart/settings` | MA configs for charts |

## Server

**IP**: 65.20.83.178 | **User**: uma

### Systemd Service
```bash
systemctl --user status fastapi_app.service
systemctl --user restart fastapi_app.service
```

### Debug Commands
```bash
curl -s http://127.0.0.1:8000/api/schedule
curl -s http://127.0.0.1:8000/api/logic/status
tail -20 /home/uma/no_env/uma_scalper/data/log.txt
```

## Schedule

- **Start**: 00:05 (test), 09:14 (production)
- **End**: 15:31 (test), 23:59 (production)
- **Days**: Mon-Fri

## Trading Flow

1. **Outside Schedule**: Shows sleeping.html (countdown, schedule info)
2. **Within Schedule**: Shows logic.html + auto-starts trading
3. **Trading**: TickRunner executes trades based on Strategy

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | Controller (APScheduler, routes) |
| `src/logic_app.py` | Trading start/stop functions |
| `src/state.py` | LogicState singleton |
| `src/api.py` | Broker API wrapper |
| `src/tickrunner.py` | Trade execution state machine |
| `src/strategy.py` | ATM selection, premium matching |
| `src/wserver.py` | WebSocket manager |
| `templates/sleeping.html` | Sleep page UI |
| `templates/logic.html` | Trading page UI |