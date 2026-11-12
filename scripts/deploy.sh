#!/bin/bash
# Deploy to server - update toolkit dep, commit, push, pull, uv sync, restart in one command
# NOTE: the app is pinned to the remote IP - never attempt to run it locally.
set -e

# "uma" = SSH config alias (user, IP, key live in ~/.ssh/config - never in this repo)
SERVER="uma"
SERVICE="fastapi_app.service"

echo "=== Deploy to Server ($SERVER) ==="

# 0. Refresh toolkit (git dependency) to latest and re-lock
echo "--- Updating toolkit to latest ---"
if command -v uv >/dev/null 2>&1; then
    UV=uv
else
    UV="$HOME/.local/bin/uv"
fi
$UV update toolkit || echo "WARN: uv update toolkit failed, deploying with locked rev"

# 1. Commit and push local changes (includes uv.lock change if any)
git add -A
git commit --allow-empty -m "${1:-auto: deploy}"
git push

# 2. Pull code, sync deps (uv - no pip in this venv), restart cleanly
# Project dir comes from the systemd unit's WorkingDirectory - no paths hardcoded here
ssh $SERVER "
    set -e
    cd \$(systemctl --user show $SERVICE -p WorkingDirectory --value)
    echo '--- git pull ---'
    git pull
    echo '--- uv sync ---'
    UV=\$(command -v uv || echo \$HOME/.local/bin/uv)
    \$UV sync --frozen
    systemctl --user restart $SERVICE
"

# 3. Wait for startup
sleep 5

# 4. Health check (app responds on localhost even before auth)
echo "Testing endpoint..."
RESULT=$(ssh $SERVER "curl -s -m 10 http://127.0.0.1:8000/api/schedule")

if [[ "$RESULT" == *"within_schedule"* ]]; then
    echo "✅ Deploy successful!"
    echo "Open the app at its public URL and log in with your credentials."
else
    echo "❌ Deploy failed. Service output:"
    ssh $SERVER "systemctl --user status $SERVICE --no-pager -n 10; tail -5 $PROJECT/data/log.txt"
    exit 1
fi

echo "=== Done ==="
