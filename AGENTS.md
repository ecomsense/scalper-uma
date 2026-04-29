# Scalper-UMA - Agent Context

> Operate based on `~/.claude/rules.md` (global rules)
> See [SPEC.md](SPEC.md) for High Level Design (HLD)
> See [BUILD.md](BUILD.md) for implementation details

## Architecture

```
Controller (main.py) → Logic App → TickRunner → Strategy → Broker API
```

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

## Route Structure

| Path | Description |
|------|-------------|
| `/` | Root - sleeping or logic page based on schedule |
| `/api/logic/start` | Start trading session |
| `/api/logic/stop` | Stop trading session |
| `/api/logic/status` | Running, paused, pause_reason |
| `/api/summary` | Positions, orders, m2m, realized_pnl |
| `/sse/candlesticks/{symbol}` | Live OHLC candles |
| `/sse/orders` | Order updates stream |

## Server

**User**: uma | **Service**: `fastapi_app` (systemd)

```bash
systemctl --user status fastapi_app
systemctl --user restart fastapi_app
journalctl --user -u fastapi_app -n 20
```

## Known Issues & Fixes

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

## Issue Workflow

1. **Check**: Search AGENTS.md and git history for existing issue
2. **If exists**:
   - Could be regression from another fix - trace what changed with git log
   - Fix not fully documented - add to AGENTS.md
3. **If new**: User opens GitHub issue, I reference issue # in commits
4. **Shell commands**: Create in `scripts/` directory first (not in git), reference in AGENTS.md
5. **Code changes**: Commit with `fix/feat #<issue>` message

## Milestones

- `milestone/sse-fix` - SSE candlesticks: check symbol in dict values not keys
- `milestone/migration-complete` - Latest: session TTL, schedule 09:15, UI fixed
- `milestone/ui-fully-complete` - Responsive layouts, bottom panel
- `milestone/app-footer-fixed` - Consolidated CSS, shared components