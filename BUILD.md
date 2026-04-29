# Scalper-UMA - Implementation Guide

> Operate based on `~/.claude/rules.md` (global rules)
> See [SPEC.md](SPEC.md) for High Level Design (HLD)

## Known Issues & Fixes (Do Not Repeat)

### Cancel Button Not Working
- **Symptom**: Click does nothing
- **Root Cause**: Status check used lowercase `trigger_pending` but broker API returns uppercase `TRIGGER_PENDING`
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

### SSE Candlesticks Not Streaming
- **Symptom**: SSE endpoint returns no data for options charts
- **Root Cause**: `tokens_nearest` is a dict `{ws_token: trading_symbol}`. SSE lookup was checking if symbol in dict keys (`if symbol in token_symbols`), but chart passes trading_symbol (dict value), not the ws_token key.
- **Fix**: Check `if symbol in token_symbols.values()` instead of `if symbol in token_symbols`
- **pre**: test_sse_endpoint.sh
- **commit**: dd3e57d
- **post**: verify_sse_stream.sh

**Lesson:** Always use instance variables for per-instance state!

### Settings Not Reloading After Save
- **Symptom**: MA settings changed but not reflected in trading logic
- **Root Cause**: O_SETG was cached in memory and not reloaded
- **Fix**: Set `src.constants._loaded = False` after saving settings
- **pre**: check_server_responding.sh
- **commit**: 361f6c0
- **post**: verify_settings_reload.sh

### Server Hung After Settings Change
- **Symptom**: Server stops responding after changing settings
- **Root Cause**: Stale app.pid file causes PID lock conflict
- **Fix**: Delete app.pid before restart
- **pre**: check_server_responding.sh
- **commit**: 901114a
- **post**: verify_settings_reload.sh

## Troubleshooting Guide

### Service Not Starting
1. Check systemd: `systemctl --user status fastapi_app`
2. If failed: `journalctl --user -u fastapi_app -n 20` for error details
3. Restart: `systemctl --user restart fastapi_app`
4. If port in use: `pkill -f 'python.*uvicorn'` then restart
5. If PID lock issue: `rm -f data/app.pid && systemctl --user restart fastapi_app`

### API Returning Empty Data
1. Check systemd logs: `journalctl --user -u fastapi_app -n 50`
2. Check app logs: `tail -50 /home/uma/no_env/uma_scalper/data/log.txt`
3. Force fresh session: Helper._api = None before calling Helper.api()

### Charts Not Displaying
1. Check SSE: `curl -s http://127.0.0.1:8000/sse/candlesticks/SYMBOL`
2. If historical empty, chart.js now uses live SSE data
3. If SSE returns nothing, check that logic is running (`/api/logic/status` shows `running: true`)

### Bottom Panel Not Updating
1. Check: summary.js has auto-fetch enabled
2. Refresh interval: 5 seconds

### General Debug
1. Always check systemd: `systemctl --user status fastapi_app`
2. Check systemd logs: `journalctl --user -u fastapi_app -f`
3. Check app logs: `tail -50 /home/uma/no_env/uma_scalper/data/log.txt`

## Best Practices

### Use Systemd for FastAPI Apps
- Always use `systemctl --user start/restart/stop fastapi_app`
- Check logs with `journalctl --user -u fastapi_app`
- Never start uvicorn directly

### Recommended Log Level
**`level: 20` (INFO)** in settings.yml - filters spam (`Using existing session` every 500ms) while keeping important events (session start/stop, entry CANCELED, trade checks, errors).

### Always Use Instance Variables
For FastAPI state (Wserver, Helper, etc.): use instance variables `self.xxx`, not class variables `Wserver.xxx`. Class variables are shared across all instances!

### Key Debug Commands
```bash
systemctl --user status fastapi_app     # Check ONE process via systemd
journalctl --user -u fastapi_app -n 20  # Check systemd logs
tail -20 /home/uma/no_env/uma_scalper/data/log.txt
curl -s http://127.0.0.1:8000/api/logic/status
```

## Issue Workflow

1. **Check**: Search BUILD.md and git history for existing issue
2. **If exists**:
   - Could be regression from another fix - trace what changed with git log
   - Fix not fully documented - add to BUILD.md
3. **If new**: User opens GitHub issue, I reference issue # in commits
4. **Shell commands**: Create in `scripts/` directory first (not in git), reference in BUILD.md
5. **Code changes**: Commit with `fix/feat #<issue>` message

## Scripts Directory

Store server/system commands in `scripts/` for reproducibility:
- Restart commands
- Log inspection
- Process management

Scripts are not committed to git (see `.gitignore: scripts/`).

## Milestones

- `milestone/sse-fix` - SSE candlesticks: check symbol in dict values not keys
- `milestone/migration-complete` - Latest: session TTL, schedule 09:15, UI fixed
- `milestone/ui-fully-complete` - Responsive layouts, bottom panel
- `milestone/app-footer-fixed` - Consolidated CSS, shared components