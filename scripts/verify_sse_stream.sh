#!/bin/bash
# Verify SSE candles are streaming properly

SERVER="uma@65.20.83.178"
PORT="8000"

# Get trading symbols
SYMBOLS=$(ssh $SERVER "curl -s http://127.0.0.1:$PORT/api/symbols" 2>/dev/null)
SYM=$(echo $SYMBOLS | python3 -c "import sys,json; print(json.load(sys.stdin)[0])" 2>/dev/null)

if [ -z "$SYM" ]; then
    echo "FAIL: No symbols found"
    exit 1
fi

# Test SSE and capture output
OUTPUT=$(timeout 3 ssh $SERVER "curl -sN http://127.0.0.1:$PORT/sse/candlesticks/$SYM" 2>&1)

if echo "$OUTPUT" | grep -q "live_update"; then
    echo "PASS: SSE candles streaming"
    echo "$OUTPUT" | head -c 200
else
    echo "FAIL: No live_update events"
    echo "$OUTPUT"
    exit 1
fi