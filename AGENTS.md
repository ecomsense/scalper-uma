# Scalper-UMA Agent Context

## Project
Real-time options trading bot (FastAPI + Finvasia broker API).

## Key Components
| Component | File | Purpose |
|-----------|------|---------|
| `Helper` | `src/api.py` | Broker API wrapper (singleton) |
| `Wserver` | `src/wserver.py` | WebSocket manager |
| `TickRunner` | `src/tickrunner.py` | Trade execution state machine |
| `Strategy` | `src/strategy.py` | ATM selection and premium matching |

## Server
- **IP**: 65.20.83.178 | **User**: uma
- **Port**: 8000

## Server Management
**DO NOT use systemctl!** - spawns multiple uvicorn processes causing race conditions.

```bash
# Kill and start fresh
ssh uma@65.20.83.178 'pkill -9 -f uvicorn; cd /home/uma/no_env/uma_scalper && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 >> data/log.txt 2>&1 &'
```
Always check: `ps aux | grep uvicorn` - must show ONE process.

## Configuration
- Credentials: `{project-name}_.yml` (e.g., `scalper-uma.yml`)
- Settings: `data/settings.yml`
- Trade state: `data/trade.json`

## Order Flow
1. **Frontend**: `High` → `order_type: SL`, `MKT` → `order_type: LMT`
2. **Backend**: `@app.post(/api/trade/buy)` → `Helper.one_side()`
3. **Broker**: `cls.api().order_place(**bargs)`

## Key Rules
1. Always call `Helper.api()` before broker API calls - session may be invalid
2. Never run multiple uvicorn processes - singleton breaks
3. Modal fetch must be async - wait for data before showing
4. Auto-fetch on page load - else stale/empty data
5. Never string comparison for time - use integers
6. Broker API returns UPPERCASE status: `TRIGGER_PENDING`, not `trigger_pending`
7. `order_cancel()` only accepts `order_id`, not `quantity`

## Common Bugs

### Cancel button not working
- Status check used lowercase: `if status in ['OPEN', 'trigger_pending', 'PENDING']`
- Fix: `if status in ['OPEN', 'TRIGGER_PENDING', 'PENDING']`
- `order_cancel()` doesn't accept `quantity` kwarg: `cls.api().order_cancel(order_id=o.get('order_id'))`

### Logs modal empty
- `loadLogs()` function not defined - add it:
```javascript
function loadLogs() {
    fetch('/api/admin/logs').then(r=>r.json()).then(d=>document.getElementById('logsEditor').value=d.content).catch(e=>{});
}
```
- Auto-load on open:
```javascript
function openLogsModal() {
    document.getElementById('logsModal').style.display='block';
    loadLogs();
}
```

### JavaScript outside script tag
- `</script>` placed too early in main.py HTML string
- All code after it becomes plain text

### Logs not writing to file
- `settings.yml`: `log.show: true` required (false = console only)

### Bottom panel shows 0 orders
- Multiple uvicorn processes - kill all and restart single

## Debug Commands
```bash
ps aux | grep uvicorn | grep -v grep
tail -20 /home/uma/no_env/uma_scalper/data/log.txt
grep -i cancel /home/uma/no_env/uma_scalper/data/log.txt | tail -5
curl -s http://127.0.0.1:8000/api/trade/sell?symbol=NIFTY28APR26P24000&ltp=5
curl -s http://127.0.0.1:8000/api/admin/logs | head -c 500
```

## Bottom Panel Format
Shows `open_orders / total_orders` (active orders = OPEN/TRIGGER_PENDING/PENDING).

## Recommended Log Level
**`level: 20` (INFO)** - filters spam (`Using existing session` every 500ms) while keeping important events (session start/stop, entry CANCELED, trade checks, errors).