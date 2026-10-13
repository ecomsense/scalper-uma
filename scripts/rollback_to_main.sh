#!/bin/bash
# Rollback to main branch. Run on server as uma.
# Restores main, restarts service, verifies. data/ is gitignored (untouched).
set -e
cd /home/uma/no_env/uma_scalper
git rev-parse HEAD > /tmp/branch_commit.txt
echo "Leaving $(cat /tmp/branch_commit.txt), returning to main"
git fetch origin
git checkout main
git pull --ff-only
systemctl --user restart fastapi_app.service
sleep 3
systemctl --user status fastapi_app.service --no-pager -l | head -8
curl -s http://127.0.0.1:8000/api/schedule; echo
