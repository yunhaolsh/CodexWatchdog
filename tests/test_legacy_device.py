import json
import struct

from daemon.protocol import TaskStatus
from daemon.ws_server import StackChanWebSocketServer


def test_legacy_status_uses_existing_text_message_frame():
    server = StackChanWebSocketServer("test-token", legacy_device=True)
    frame = server._encode_status(TaskStatus("t1", "running", title="执行中 / Working"))
    assert frame[0] == 0x07
    length = struct.unpack(">I", frame[1:5])[0]
    payload = json.loads(frame[5:])
    assert length == len(frame[5:]) and payload == {"name": "CodexWatchdog", "content": "执行中 / Working"}
