#!/bin/bash
# Check if server is responding

SERVER_IP=${1:-65.20.83.178}

echo -n 'Checking server response... '
if timeout 3 ssh uma@$SERVER_IP 'curl -s http://127.0.0.1:8000/api/schedule' > /dev/null 2>&1; then
    echo 'OK'
    ssh uma@$SERVER_IP 'curl -s http://127.0.0.1:8000/api/schedule'
else
    echo 'FAIL'
    exit 1
fi