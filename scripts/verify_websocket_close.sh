#!/bin/bash
# Post-fix: Verify websocket closes properly after restart

echo "Checking new code for close_websocket usage..."
grep -n "close_websocket" ~/no_env/uma_scalper/src/logic_app.py

echo ""
echo "Checking if websocket errors resolved after restart..."

# Test multiple restarts
for i in 1 2 3; do
    echo "Test $i: Stop and restart trading session..."
    curl -s -X POST http://127.0.0.1:8000/api/logic/stop
    sleep 2
    curl -s -X POST http://127.0.0.1:8000/api/logic/start
    sleep 3

    # Check recent logs for socket errors
    ERRORS=$(tail -20 ~/no_env/uma_scalper/data/log.txt | grep -c "socket is already opened" || echo "0")
    echo "Socket errors in last 20 log lines: $ERRORS"
done

echo ""
echo "If socket errors = 0 for all tests, fix is working"