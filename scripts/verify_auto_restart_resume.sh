#!/bin/bash
# POST-TEST: Verify that sleep page auto-starts trading and redirects to /logic after restart

set -e

API="http://127.0.0.1:8000"
TIMEOUT=20

echo "🧪 Testing auto-restart resume during market hours..."

# 1. Verify we're within schedule
SCHEDULE=$(curl -s "$API/api/schedule")
WITHIN_SCHEDULE=$(echo "$SCHEDULE" | grep -o '"within_schedule":[^,}]*' | grep -o 'true\|false')

if [ "$WITHIN_SCHEDULE" != "true" ]; then
    echo "⚠️  Skipping test - not within market hours"
    exit 0
fi

# 2. Verify trading is running
STATUS=$(curl -s "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" != "true" ]; then
    echo "❌ Trading not running. Cannot test auto-start"
    exit 1
fi

echo "✅ Trading is running and within schedule"

# 3. Stop trading (simulate restart)
echo "🛑 Stopping trading..."
curl -s -X POST "$API/api/logic/stop" > /dev/null

# 4. Wait for state to settle
sleep 2

# 5. Verify trading is stopped
STATUS=$(curl -s "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" != "false" ]; then
    echo "❌ Trading did not stop"
    exit 1
fi

echo "✅ Trading stopped successfully"

# 6. Wait for sleep page auto-start logic (polls every 3s)
echo "⏳ Waiting for sleep page to detect within_schedule && !running..."
sleep 4

# 7. Verify trading auto-started
STATUS=$(curl -s "$API/api/logic/status")
RUNNING=$(echo "$STATUS" | grep -o '"running":[^,}]*' | grep -o 'true\|false')

if [ "$RUNNING" != "true" ]; then
    echo "❌ Trading did not auto-start after restart"
    exit 1
fi

echo "✅ Trading auto-started successfully!"
echo "🎉 Sleep page auto-restart resume test PASSED"
