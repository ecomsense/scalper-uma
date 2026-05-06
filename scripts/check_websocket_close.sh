#!/bin/bash
# Pre-check: Verify current websocket close implementation

echo "Checking current code for ws.close usage..."
grep -n "ws.close\|ws.close_websocket" ~/no_env/uma_scalper/src/logic_app.py

echo ""
echo "Test restart by stopping and starting trading session:"
echo "1. Stop trading: curl -X POST http://127.0.0.1:8000/api/logic/stop"
echo "2. Start trading: curl -X POST http://127.0.0.1:8000/api/logic/start"
echo "3. Check logs for 'socket is already opened' errors"