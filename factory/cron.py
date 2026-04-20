#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
import os

os.chdir("/home/uma/no_env/uma_scalper")
action = sys.argv[1] if len(sys.argv) > 1 else "start"

# Try direct systemctl without sudo (user level might work)
CMD = ["/usr/bin/systemctl", action, "uma-scalper.service"]
result = subprocess.run(CMD, capture_output=True, text=True)

# Also try with sudo in case direct fails
if result.returncode != 0:
    CMD = ["/usr/bin/sudo", action, "uma-scalper.service"]
    result = subprocess.run(CMD, capture_output=True, text=True)

# Write output to cron.txt
with open("/home/uma/no_env/uma_scalper/data/cron.txt", "a") as f:
    f.write(f"[{action}] {result.returncode} stdout:{result.stdout} stderr:{result.stderr}\n")