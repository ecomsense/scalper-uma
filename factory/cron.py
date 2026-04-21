#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
import os

os.chdir("/home/uma/no_env/uma_scalper")
action = sys.argv[1] if len(sys.argv) > 1 else "start"

# Full path and passwordless sudo via Defaults in sudoers requires no TTY
# Use subprocess with shell=False, env with XDG_RUNTIME_DIR
env = os.environ.copy()
env["XDG_RUNTIME_DIR"] = "/run/user/1001"
CMD = ["/usr/bin/sudo", "/usr/bin/systemctl", action, "uma-scalper.service"]
result = subprocess.run(CMD, capture_output=True, text=True, env=env)

# Write output to cron.txt
with open("data/cron.txt", "a") as f:
    f.write(f"[{action}] returncode:{result.returncode} stdout:{result.stdout} stderr:{result.stderr}\n")