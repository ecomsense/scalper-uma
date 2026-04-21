#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
import os

os.chdir("/home/uma/no_env/uma_scalper")
action = sys.argv[1] if len(sys.argv) > 1 else "start"

# Direct systemctl - works from user cron without sudo
CMD = ["/usr/bin/systemctl", action, "uma-scalper.service"]
result = subprocess.run(CMD, capture_output=True, text=True)

# Write output to cron.txt
with open("data/cron.txt", "a") as f:
    f.write(f"[{action}] returncode:{result.returncode} stdout:{result.stdout} stderr:{result.stderr}\n")