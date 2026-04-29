# Scalper-UMA - Implementation Details

> Operate based on `~/.claude/rules.md` (global rules)
> See [SPEC.md](SPEC.md) for High Level Design (HLD)
> See [AGENTS.md](AGENTS.md) for project issues and fixes

## Troubleshooting Quick Reference

### Service Not Starting
1. `systemctl --user status fastapi_app`
2. `journalctl --user -u fastapi_app -n 20`
3. `systemctl --user restart fastapi_app`
4. If PID lock: `rm -f data/app.pid`

### API Not Responding
1. `journalctl --user -u fastapi_app -n 50`
2. `tail -50 /home/uma/no_env/uma_scalper/data/log.txt`

### Check SSE
```bash
curl -s http://127.0.0.1:8000/sse/candlesticks/SYMBOL
```

## Scripts Directory

Scripts are stored in `scripts/` (not committed to git):
- `test_sse_endpoint.sh` - Test SSE endpoint
- `verify_sse_stream.sh` - Verify SSE streaming
- `check_server_responding.sh` - Check server health
- `verify_settings_reload.sh` - Verify settings reload

## Best Practices

- Use systemd: `systemctl --user start/restart/stop fastapi_app`
- Log level INFO (`level: 20`) to filter spam
- Always use instance variables for FastAPI state