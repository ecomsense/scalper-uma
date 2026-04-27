# Scalper-UMA Debug Session - 2026-04-27

## Goal
Debug and fix the Scalper-UMA trading bot server that wasn't starting trading sessions automatically

## Constraints & Preferences
- Don't make changes without confirming with user first
- Use DEBUG level logging (level 10)

## Progress

### Done
- Found old process holding port 8000 blocking restarts - killed ghost processes
- Found service was crashing (exit code 1, restart counter 762+)
- Found websocket not opening (start_websocket returned None)
- Found lifespan code not executing (no "Within schedule" logs)
- Fixed logging level: was hardcoded to 30 (WARNING), now reads from settings.yml (level 10 = DEBUG)
- Fixed wserver.py: socket_opened was class variable, changed to instance variable
- Added detailed logging to lifespan and trading_session_start functions
- Trading session now starts automatically on server restart
- Enabled chart scripts in frontend (lightweight-charts CDN and chart.js were commented out)
- Fixed chart not displaying: initialize with live data when historical is empty
- Enabled auto-fetch for bottom panel with 5s refresh
- Fixed summary API returning empty data - root cause was ghost process holding port

### In Progress
- (none)

### Blocked
- (none)

## Key Findings & Fixes

### 1. Ghost Process Issue (CRITICAL)
**Symptom**: API endpoints returning empty data, code changes not taking effect
**Root Cause**: Old uvicorn process holding port 8000, new service failing to start with "address already in use"
**Fix**: Always use `pkill -9 -f uvicorn` before restart, not just `pkill`

### 2. Trading Session Not Starting
**Root Cause**: socket_opened was class variable instead of instance variable in Wserver
**Fix**: Changed to instance variable in wserver.py

### 3. Chart Not Displaying
**Root Cause**: Broker's historical data returns None for options, chart.js was blocking live updates when historical was empty
**Fix**: Modified chart.js to initialize with first live candle when historical is empty

### 4. Bottom Panel Not Updating
**Root Cause**: Auto-fetch was disabled in summary.js
**Fix**: Enabled auto-fetch on page load with 5-second refresh interval

### 5. Summary API Empty
**Root Cause**: Ghost process issue - the running server was old code
**Fix**: Killed ghost process properly, now working

## Current State
- Server running: YES (PID with 13 tasks, 84.5MB memory)
- Trading session: ACTIVE
- LTP updates: FLOWING (199 symbols)
- Charts: DISPLAYING live data
- Orders API: WORKING (7 orders from mobile + web)
- Positions API: WORKING (2 closed positions)
- Realized P&L: 123.50

## Next Steps
- None currently - all issues resolved

## Critical Context
- Server IP: 65.20.83.178, user: uma
- Service: fastapi_app.service
- Log file: /home/uma/no_env/uma_scalper/data/log.txt

## Key Takeaways
1. Always kill ghost processes with `pkill -9 -f uvicorn` before restart
2. Check service memory/tasks to verify proper startup (should be ~80MB, 10+ tasks)
3. Check log for "address already in use" errors
4. Broker historical API returns None for options - use live SSE data instead
5. Always verify code changes are actually running on server