#!/usr/bin/env python3
import subprocess
import sys
import os
import signal

os.chdir("/home/uma/no_env/uma_scalper")
action = sys.argv[1] if len(sys.argv) > 1 else "start"

VENV_PY = "/home/uma/no_env/uma_scalper/.venv/bin/python"
LOG = "/home/uma/no_env/uma_scalper/data/log.txt"

def start():
    subprocess.Popen([VENV_PY, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"],
                   stdout=open(LOG, "a"), stderr=subprocess.STDOUT)

def stop():
    subprocess.run(["pkill", "-f", "uvicorn.*8000"])

if action == "start":
    start()
elif action == "stop":
    stop()

with open("data/cron.txt", "a") as f:
    f.write(f"[{action}] ok\n")