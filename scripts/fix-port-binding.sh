#!/bin/bash
# Fix port binding issue - add ExecStartPre to kill existing process on port 8000
SERVICE_FILE="$HOME/.config/systemd/user/fastapi_app.service"

if ! grep -q "ExecStartPre" "$SERVICE_FILE"; then
    sed -i 's|ExecStart=|ExecStartPre=/bin/fuser -k 8000/tcp 2>/dev/null || true\nExecStart=|' "$SERVICE_FILE"
    systemctl --user daemon-reload
    echo "Fixed: Added ExecStartPre to kill port 8000 before starting"
else
    echo "Already fixed"
fi