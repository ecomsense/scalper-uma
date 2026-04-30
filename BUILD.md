# Build & Deployment Guide

## Quick Start

```bash
# Clone and setup
git clone https://github.com/ecomsense/scalper-uma.git
cd scalper-uma
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Run locally (dev only)
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Production Deployment

### Server: uma@65.20.83.178

```bash
# Check service status
systemctl --user status fastapi_app.service

# Restart service (ALWAYS use systemctl, never uvicorn directly)
systemctl --user restart fastapi_app.service

# View logs
tail -f /home/uma/no_env/uma_scalper/data/log.txt
```

## Systemd Service

Service file location: `/home/uma/.config/systemd/user/fastapi_app.service`

Key settings:
- **Restart**: always (with 5s delay)
- **Logging**: stdout/stderr → data/log.txt
- **SKIP_PID_LOCK**: 1 (to prevent false positive lock errors)

## Schedule

| Setting | Value |
|---------|-------|
| Start | 09:15 IST |
| End | 15:31 IST |
| Days | Mon-Fri (0-4) |

Configured in: `src/main.py` → `ScheduleConfig` class

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root - serves sleeping.html or logic.html |
| `/api/schedule` | GET | Schedule info, within_schedule, times |
| `/api/logic/start` | POST | Start trading session |
| `/api/logic/stop` | POST | Stop trading session |
| `/api/logic/status` | GET | Running, paused, pause_reason |
| `/api/summary` | GET | Positions, orders, m2m, realized_pnl |
| `/api/chart/settings` | GET | MA configuration for charts |
| `/api/admin/settings` | GET/POST | Read/write settings.yml |
| `/api/admin/reset` | POST | Reset Helper and startup_data |
| `/api/admin/logs` | GET | Server log content |

## Settings

Location: `data/settings.yml`

Example:
```yaml
log:
  show: true
  level: 10
base: NIFTY
ma:
  - type: ema
    period: 3
    price: low
    color: red
  - type: ema
    period: 5
    price: close
    color: blue
NIFTY:
  symbol: NIFTY
  option_exchange: NFO
  lots: 1
  profit: 0.90
  premium: 40
```

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | Controller, ScheduleConfig, routes |
| `src/logic_app.py` | Trading session start/stop, lifecycle |
| `src/state.py` | LogicState singleton |
| `src/api.py` | Helper.api() with session TTL (7h) |
| `src/tickrunner.py` | Trade execution state machine |
| `src/strategy.py` | ATM selection, premium matching |
| `src/wserver.py` | WebSocket manager |
| `src/constants.py` | Settings loader (O_SETG, O_CNFG) |
| `templates/logic.html` | Trading charts + bottom panel |
| `templates/sleeping.html` | Countdown page |
| `src/static/chart.js` | Chart.js with MA color support |
| `src/static/summary.js` | Orders table, positions |

## Testing Scripts

```bash
# Pre-test scripts (scripts directory - gitignored)
scripts/check_server_responding.sh
scripts/check_restart_during_hours.sh
scripts/check_settings_reload.sh

# Post-test scripts
scripts/verify_settings_reload.sh
scripts/verify_auto_restart_resume.sh
scripts/verify_settings_reset_flow.sh
```

## Troubleshooting

1. **Service not responding**: Check `systemctl --user status fastapi_app.service`
2. **Port 8000 in use**: `netstat -tlnp | grep 8000` or `ss -tlnp | grep 8000`
3. **Logs**: `tail -100 /home/uma/no_env/uma_scalper/data/log.txt`
4. **PID lock issues**: Already handled with SKIP_PID_LOCK=1

## Deployment Commands

```bash
# Local commit & push
git add -A && git commit -m 'message' && git push

# Server pull & restart
ssh uma@65.20.83.178 "cd /home/uma/no_env/uma_scalper && git pull && systemctl --user restart fastapi_app.service"
```