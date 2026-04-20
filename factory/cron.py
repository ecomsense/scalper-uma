#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys

action = sys.argv[1] if len(sys.argv) > 1 else "start"
CMD = ["/usr/bin/sudo", "/usr/bin/systemctl", action, "uma-scalper.service"]
result = subprocess.run(CMD, capture_output=True, text=True)
print(f"{CMD} stdout: {result.stdout}", file=sys.stderr)
print(f"{CMD} stderr: {result.stderr}", file=sys.stderr)