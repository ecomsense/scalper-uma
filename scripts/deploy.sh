#!/bin/bash
# Deploy - RUN THIS ON THE REMOTE SERVER (not locally).
# Updates the toolkit dependency, pulls latest code, syncs deps (uv), restarts the app.
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

echo "--- toolkit: latest (uv.lock updated here so the commit is ready to push back) ---"
"$UV" update toolkit || echo "WARN: uv update toolkit failed, deploying with locked rev"
if ! git diff --quiet uv.lock; then
    git add uv.lock
    git commit -m "auto: bump toolkit lock on server"
    git push || echo "WARN: could not push lock bump (no push access on server?) - deploy continues with local lock"
fi

echo "--- uv sync ---"
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
