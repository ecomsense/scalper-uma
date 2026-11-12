#!/bin/bash
# Deploy - RUN THIS ON THE REMOTE SERVER (not locally).
# Remote's only job: pull what was pushed (code + uv.lock bumps, incl. toolkit)
# and sync the venv to the pushed lockfile. No package resolution happens here.
set -e

SERVICE="fastapi_app.service"

echo "=== Deploy on $(hostname) ==="

# Project dir comes from the systemd unit's WorkingDirectory - no paths hardcoded
APP_DIR="$(systemctl --user show $SERVICE -p WorkingDirectory --value)"
cd "$APP_DIR"
echo "App dir: $APP_DIR"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

echo "--- git pull ---"
git pull

echo "--- uv sync (installs exactly the pushed uv.lock, incl. git deps like toolkit) ---"
"$UV" sync --frozen

echo "--- restart $SERVICE ---"
systemctl --user restart $SERVICE
sleep 5

echo "--- health check ---"
RESULT=$(curl -s -m 10 http://127.0.0.1:8000/api/schedule)
if [[ "$RESULT" == *"within_schedule"* ]]; then
    echo "✅ Deploy successful!"
    echo "Open the app at its public URL and log in with your credentials."
else
    echo "❌ Deploy failed. Service output:"
    systemctl --user status $SERVICE --no-pager -n 10
    tail -5 "$APP_DIR/data/log.txt"
    exit 1
fi

echo "=== Done ==="
