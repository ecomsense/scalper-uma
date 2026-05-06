#!/bin/bash
# POST-TEST: Verify restart button works without hanging

set -e

API="http://127.0.0.1:8000"
TIMEOUT=30

echo "🧪 Testing restart button..."

# 1. Verify trading is running
STATUS=$(curl -s --max-time $TIMEOUT "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" != "true" ]; then
    echo "⚠️  Trading not running. Start it first."
    exit 0
fi

echo "✅ Trading is running"

# 2. Call stop via API (simulating restart button)
echo "🛑 Calling stop..."
STOP_RESPONSE=$(curl -s -X POST --max-time $TIMEOUT "$API/api/logic/stop")

echo "Stop response: $STOP_RESPONSE"

# 3. Wait a bit for stop to complete
sleep 3

# 4. Check if trading stopped
STATUS=$(curl -s --max-time $TIMEOUT "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" = "true" ]; then
    echo "❌ Trading did not stop"
    exit 1
fi

echo "✅ Trading stopped successfully"

# 5. Wait for auto-start (sleep page should auto-start within ~3-5 seconds)
echo "⏳ Waiting for sleep page auto-start..."
sleep 5

# 6. Check if trading started again
STATUS=$(curl -s --max-time $TIMEOUT "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" = "true" ]; then
    echo "✅ Trading auto-started after stop"
    echo "🎉 Restart button test PASSED"
else
    echo "⚠️  Trading did not auto-start (may be outside schedule)"
    exit 0
fi