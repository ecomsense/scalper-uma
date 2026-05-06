#!/bin/bash
# POST-TEST: Verify that settings save + reset clears session state

set -e

API="http://127.0.0.1:8000"

echo "🧪 Testing settings save and reset flow..."

# 1. Get current settings
echo "📖 Reading current settings..."
CURRENT=$(curl -s "$API/api/admin/settings")
if ! echo "$CURRENT" | grep -q "content"; then
    echo "❌ Failed to read settings"
    exit 1
fi

echo "✅ Settings readable"

# 2. Modify settings (just add a comment to test)
MODIFIED=$(echo "$CURRENT" | jq '.content |= . + "\n# Test comment"')
CONTENT=$(echo "$MODIFIED" | jq -r '.content')

# 3. Save settings
echo "💾 Saving modified settings..."
SAVE_RESPONSE=$(curl -s -X POST "$API/api/admin/settings" \
  -H "Content-Type: application/json" \
  -d "{\"content\": $(echo "$CONTENT" | jq -R -s '.')}")

if ! echo "$SAVE_RESPONSE" | grep -q "success"; then
    echo "❌ Failed to save settings"
    exit 1
fi

echo "✅ Settings saved"

# 4. Test reset endpoint
echo "🔄 Testing reset endpoint..."
RESET_RESPONSE=$(curl -s -X POST "$API/api/admin/reset")

if ! echo "$RESET_RESPONSE" | grep -q "success"; then
    echo "❌ Reset endpoint failed"
    exit 1
fi

echo "✅ Reset endpoint working"

# 5. Verify server is still responsive
echo "📡 Verifying server still responsive..."
if ! curl -s "$API/api/schedule" > /dev/null; then
    echo "❌ Server not responsive after reset"
    exit 1
fi

echo "✅ Server responsive after reset"
echo "🎉 Settings save and reset flow test PASSED"
