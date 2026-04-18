#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys

action = sys.argv[1] if len(sys.argv) > 1 else "start"

if action == "start":
    subprocess.run(["/usr/bin/sudo", "/usr/bin/systemctl", "start", "uma-scalper.service"])
elif action == "stop":
    subprocess.run(["/usr/bin/sudo", "/usr/bin/systemctl", "stop", "uma-scalper.service"])
elif action == "restart":
    subprocess.run(["/usr/bin/sudo", "/usr/bin/systemctl", "restart", "uma-scalper.service"])