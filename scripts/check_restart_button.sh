#!/bin/bash
# PRE-TEST: Verify server is responsive before testing restart button

set -e

API="http://127.0.0.1:8000"
TIMEOUT=10

echo "🔍 Checking server health..."
if ! curl -s --max-time $TIMEOUT "$API/api/schedule" > /dev/null; then
    echo "❌ Server not responding. Start with: systemctl --user start fastapi_app.service"
    exit 1
fi

echo "✅ Server is responsive"

# Check schedule is within hours
SCHEDULE=$(curl -s "$API/api/schedule")
WITHIN=$(echo "$SCHEDULE" | grep -o '"within_schedule":[^,}]*' | grep -o 'true\|false')

echo "⏰ Within schedule: $WITHIN"

if [ "$WITHIN" != "true" ]; then
    echo "⚠️  Not within market hours for restart test"
    exit 0
fi

echo "📋 Pre-test complete. Ready to test restart button."