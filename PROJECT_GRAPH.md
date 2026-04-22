# Scalper-UMA Project Graph

## Repository Structure

```
scalper-uma/
├── src/
│   ├── api.py           # Helper (broker API wrapper, singleton pattern)
│   ├── main.py          # FastAPI app + endpoints
│   ├── strategy.py      # ATM selection + premium matching
│   ├── tickrunner.py    # Trade execution state machine
│   ├── symbol.py        # Symbol/token management
│   ├── wserver.py       # WebSocket manager
│   └── __pycache__/     # Cached bytecode
├── factory/
│   └── cron.py          # Cron-based server start/stop
├── data/
│   ├── settings.yml     # App settings (profit, quantity, etc.)
│   └── trade.json       # Persistent trade state
├── static/
│   └── chart.js         # Frontend chart with price lines
└── AGENTS.md            # Agent context & procedures
```

## Key Architecture

### Server Architecture
- **FastAPI** (uvicorn) runs 24/7 on port 8000
- **APScheduler** manages trading sessions:
  - Start: 9:14 AM IST weekdays (9:14 + 0:30 buffer)
  - Stop: 3:15 PM IST weekdays (3:15 + 0:00 buffer)
- Settings save → restart trading session (not server)
- Systemd user service: `~/.config/systemd/user/fastapi_app.service`

### Trading Flow
```
1. Server start → FastAPI + APScheduler
   ├─ Helper.api() creates broker session
   └─ Schedule: start_session / stop_session

2. WebSocket (Wserver) subscribes to multiple symbols
   └─ Provides LTP for all subscribed tokens

3. Strategy calculates ATM from LTP
   └─ Gets tokens for ATM + surrounding strikes

4. TickRunner processes trades
   ├─ Loads trade.json for state
   ├─ Places entry order
   ├─ On fill → place stop loss + target
   └─ Monitors LTP for exit conditions

5. Client (chart.js) connects via SSE
   ├─ /api/chart/candlesticks (SSE)
   └─ /api/chart/settings (REST)
```

## Recent Fixes

### 2026-04-22: Chart Profit Setting
- **Problem**: Frontend TGT ignored `settings.yml` profit, used default 5 points
- **Root**: `/api/chart/settings` returned only `ma`, not `profit`
- **Fix**: `src/main.py` reads `O_SETG[base].profit` and includes in response

### 2026-04-22: Ghost Processes
- **Problem**: Code changes not taking effect after restart
- **Root**: Multiple uvicorn processes (old + new)
- **Fix**: `pkill -f uvicorn` before restart
- **Note**: Systemd user service preferred over cron

### 2026-04-21: Multiple Symbol LTP
- **Problem**: Exit orders not triggering modify (LTP was None)
- **Root**: TickRunner only subscribed to ATM symbol tokens
- **Fix**: Pass all 198 subscribed tokens to TickRunner

### 2026-04-21: Trade.json Sync
- **Problem**: TickRunner's `entry_id` never matched API's saved ID
- **Root**: State stored only in instance var, not trade.json
- **Fix**: `_load_trade_from_file()` syncs from trade.json

## Common Commands

### Local Development
```bash
cd /home/pannet1/py/fastapi/scalper-uma
python3 -m py_compile src/main.py  # Syntax check
git add -A && git commit -m "msg" && git push
```

### Server Management
```bash
# Restart service (systemd user)
systemctl --user stop fastapi_app.service
sleep 2
systemctl --user start fastapi_app.service

# Kill all uvicorn processes (fallback)
pkill -f uvicorn && sleep 2

# Pull and restart
cd /home/uma/no_env/uma_scalper
git pull
systemctl --user stop fastapi_app.service
sleep 2
systemctl --user start fastapi_app.service
```

### Testing
```bash
curl -s http://127.0.0.1:8000/api/chart/settings
# Returns: {"ma": [...], "profit": 0.75}
```