#!/bin/bash
# PRE-TEST: Verify server is responsive before testing restart during market hours

set -e

API="http://127.0.0.1:8000"
TIMEOUT=10

echo "🔍 Checking server health..."
if ! curl -s --max-time $TIMEOUT "$API/api/schedule" > /dev/null; then
    echo "❌ Server not responding. Start with: systemctl --user start fastapi_app.service"
    exit 1
fi

echo "✅ Server is responsive"

# Check if we're within market hours
SCHEDULE=$(curl -s "$API/api/schedule")
WITHIN_SCHEDULE=$(echo "$SCHEDULE" | grep -o '"within_schedule":[^,}]*' | grep -o 'true\|false')

echo "⏰ Within schedule: $WITHIN_SCHEDULE"

if [ "$WITHIN_SCHEDULE" != "true" ]; then
    echo "⚠️  Not within market hours. Test should be run 09:15-15:31 IST (Mon-Fri)"
    echo "   You can still test the logic, but results won't reflect real market conditions"
fi

echo "📋 Pre-test complete. Ready to test restart during market hours."
