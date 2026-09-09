#!/usr/bin/env python3
"""Local process fixture: no provider calls, files changed, or external commands."""
import json
import sys
import time


def emit(payload):
    print(json.dumps(payload), flush=True)


assert sys.argv[1:3] == ["exec", "--json"]
assert sys.argv[3] == "--"
prompt = sys.argv[4]
emit({"type": "turn.started"})
emit({"type": "item.started", "item": {"type": "command_execution", "command": "mock test"}})
sys.stderr.write("diagnostic\n" * 20000)
sys.stderr.flush()
if prompt == "hang":
    time.sleep(60)
elif prompt == "fail":
    sys.exit(7)
elif prompt == "missing-completion":
    sys.exit(0)
else:
    time.sleep(0.05)
    emit({"type": "item.completed", "item": {"type": "agent_message", "text": "mock result"}})
    emit({"type": "turn.completed", "usage": {}})
    if prompt == "late-fail":
        sys.exit(8)
