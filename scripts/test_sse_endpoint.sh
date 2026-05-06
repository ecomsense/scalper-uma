#!/bin/bash
# Test SSE candlesticks endpoint returns data

SERVER="uma@65.20.83.178"
PORT="8000"

echo "Testing SSE endpoint for options symbol..."

# Get trading symbols from API
SYMBOLS=$(ssh $SERVER "curl -s http://127.0.0.1:$PORT/api/symbols" 2>/dev/null)
echo "Available symbols: $SYMBOLS"

# Pick first symbol
SYM=$(echo $SYMBOLS | python3 -c "import sys,json; print(json.load(sys.stdin)[0])" 2>/dev/null)

if [ -z "$SYM" ]; then
    echo "ERROR: No symbols found. Is logic running?"
    exit 1
fi

echo "Testing SSE with symbol: $SYM"
timeout 2 ssh $SERVER "curl -sN http://127.0.0.1:$PORT/sse/candlesticks/$SYM" 2>&1 | head -c 200

echo ""
echo "Done"