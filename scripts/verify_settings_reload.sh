#!/bin/bash
# Verify MA settings are loaded by checking app logs

SERVER_IP=${1:-65.20.83.178}

echo 'Checking for Settings loaded log...'
ssh uma@$SERVER_IP 'journalctl --user -u fastapi_app -n 50 | grep -i settings' || echo 'No Settings loaded log found - may need to start logic'

echo ''
echo 'Current chart settings API:'
ssh uma@$SERVER_IP 'curl -s http://127.0.0.1:8000/api/chart/settings'