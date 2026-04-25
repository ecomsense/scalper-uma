#!/bin/bash
# Deploy to server - pull + restart in one command
set -e

SERVER="uma@65.20.83.178"
PROJECT="/home/uma/no_env/uma_scalper"

echo "=== Deploy to Server ==="

# Kill ghost processes, pull, restart
ssh $SERVER "cd $PROJECT && git pull && pkill -f uvicorn && sleep 2 && systemctl --user start fastapi_app.service"

# Wait for startup
sleep 5

# Test endpoint
echo "Testing endpoint..."
RESULT=$(ssh $SERVER "curl -s http://127.0.0.1:8000/api/chart/settings")

if [[ "$RESULT" == *"ma"* ]]; then
    echo "✅ Deploy successful!"
else
    echo "❌ Deploy failed: $RESULT"
    exit 1
fi

echo "=== Done ==="