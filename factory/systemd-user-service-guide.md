# Systemd User Service Reference

This is a generic reference for creating systemd user services that can be used across all agentic harnesses and projects.

## Standard Service File Template

```ini
[Unit]
Description=<Your Service Description>
After=network.target

[Service]
Type=simple
# IMPORTANT: Do NOT specify User= for --user services (see Gotchas below)
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/venv/bin"
Environment="YOUR_ENV_VAR=value"

# Optional: Kill any process on port before starting
ExecStartPre=/bin/sh -c '/usr/bin/fuser -k -9 <PORT>/tcp 2>/dev/null || true'
ExecStartPre=/usr/bin/sleep 1

ExecStart=/path/to/your/venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port <PORT>

StandardOutput=append:/path/to/your/project/data/log.txt
StandardError=append:/path/to/your/project/data/log.txt

# Restart policy: on-failure is safer than always (prevents tight restart loops)
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
```

## Key Configurations Explained

| Setting | Purpose |
|---------|---------|
| `Type=simple` | Process stays in foreground (uvicorn does this) |
| `WorkingDirectory` | Where the app runs from |
| `Environment` | Set env vars (PATH, API keys, etc.) |
| `ExecStartPre` | Run commands before main process (cleanup, etc.) |
| `StandardOutput/StandardError` | Log to file instead of journalctl |
| `Restart=on-failure` | Only restart if process fails (not on clean stop) |
| `RestartSec=30` | Wait 30s between restarts (prevents tight loops) |
| `WantedBy=default.target` | Auto-start when user logs in |

## Common Commands

```bash
# Start service
systemctl --user start <service-name>

# Stop service
systemctl --user stop <service-name>

# Restart service
systemctl --user restart <service-name>

# Check status
systemctl --user status <service-name>

# View logs
journalctl --user -u <service-name> -n 50 --no-pager

# Enable auto-start on login
systemctl --user enable <service-name>

# Disable auto-start
systemctl --user disable <service-name>

# Reload systemd after changing service file
systemctl --user daemon-reload
```

## Best Practices

1. **Use absolute paths** - systemd uses minimal PATH, always use full paths
2. **Log to file** - Use StandardOutput/StandardError to append to log files
3. **Use Restart=on-failure** - Not Restart=always (prevents tight restart loops)
4. **Set RestartSec=30+** - Gives time for cleanup between restarts
5. **Clean up port before start** - Use fuser -k -9 in ExecStartPre
6. **Add sleep delay** - Wait for kernel to release socket after kill

## Common Pitfalls

### ❌ DON'T: Specify User= for --user services
```ini
# WRONG - causes "Failed to determine supplementary groups" error
User=uma
```

```ini
# CORRECT - user is implied by --user flag
# (leave User= line out entirely)
```

### ❌ DON'T: Use relative paths
```ini
# WRONG
ExecStartPre=fuser -k 8000/tcp
ExecStart=python -m uvicorn src.main:app
```

```ini
# CORRECT - use absolute paths
ExecStartPre=/usr/bin/fuser -k -9 8000/tcp
ExecStart=/home/uma/myapp/.venv/bin/python -m uvicorn src.main:app
```

### ❌ DON'T: Use Restart=always with short RestartSec
```ini
# WRONG - can cause tight restart loop during crashes
Restart=always
RestartSec=5
```

```ini
# CORRECT - safer for production
Restart=on-failure
RestartSec=30
```

### ❌ DON'T: Use systemctl (without --user) for user services
```bash
# WRONG - uses system systemd
sudo systemctl restart myapp

# CORRECT - uses user systemd
systemctl --user restart myapp
```

## Troubleshooting

### Service won't start - "Address already in use"
1. Kill process on port: `/usr/bin/fuser -k -9 <PORT>/tcp`
2. Check for zombie processes: `lsof -i :<PORT>`
3. Kill manually: `kill -9 <PID>`

### Service won't start - "Failed at step GROUP spawning"
- Usually caused by specifying `User=` in service file
- Remove the User= line (not needed for --user services)

### Service keeps restarting in tight loop
- Change `Restart=always` to `Restart=on-failure`
- Increase `RestartSec` to 30 or higher

### Logs show "fuser: not found"
- Use absolute path: `/usr/bin/fuser` instead of just `fuser`
- Or wrap in shell: `/bin/sh -c '/usr/bin/fuser -k -9 8000/tcp'`

## Deployment Checklist

1. Copy service file to `~/.config/systemd/user/<service-name>.service`
2. Run `systemctl --user daemon-reload`
3. Start service: `systemctl --user start <service-name>`
4. Check status: `systemctl --user status <service-name>`
5. Enable for auto-start: `systemctl --user enable <service-name>`

## Factory Templates

This folder contains factory templates for common services:
- `uma-scalper.service` - Python/FastAPI application
- `systemd-user-service-guide.md` - This reference

## Notes

- User services are managed by `systemd --user` (per-user)
- System services are managed by `systemd` (system-wide, requires sudo)
- User services survive until user logs out (use `loginctl enable-linger <user>` for boot persistence)
- Logs go to journalctl by default, but we append to file for easier access