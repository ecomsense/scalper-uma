#!/bin/bash
# PRE-TEST: Verify settings file is readable and server is responsive

set -e

API="http://127.0.0.1:8000"
TIMEOUT=10

echo "🔍 Checking server health..."
if ! curl -s --max-time $TIMEOUT "$API/api/schedule" > /dev/null; then
    echo "❌ Server not responding. Start with: systemctl --user start fastapi_app.service"
    exit 1
fi

echo "✅ Server is responsive"

# Check if we can read settings
echo "📋 Checking settings endpoint..."
if ! curl -s "$API/api/admin/settings" | grep -q "content"; then
    echo "❌ Settings endpoint not working"
    exit 1
fi

echo "✅ Settings endpoint working"
echo "📋 Pre-test complete. Ready to test settings save and reset."
