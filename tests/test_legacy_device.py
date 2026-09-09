import json
import asyncio
import struct

from websockets.asyncio.client import connect

from daemon.protocol import TaskStatus
from daemon.ws_server import StackChanWebSocketServer


def test_legacy_status_uses_existing_text_message_frame():
    server = StackChanWebSocketServer("test-token", legacy_device=True)
    frame = server._encode_status(TaskStatus("t1", "running", title="执行中 / Working"))
    assert frame[0] == 0x07
    length = struct.unpack(">I", frame[1:5])[0]
    payload = json.loads(frame[5:])
    assert length == len(frame[5:]) and payload == {"name": "CodexWatchdog", "content": "执行中 / Working"}


def test_unauthenticated_legacy_connection_cannot_approve():
    async def scenario():
        calls = []
        server = StackChanWebSocketServer("test-token", legacy_device=True)
        server.set_action_handler(calls.append)
        listener = await server.serve(port=0)
        try:
            port = listener.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}/stackChan/ws", proxy=None) as ws:
                await ws.send('{"type":"hello"}')
                assert (await ws.recv())[0] == 7
                await ws.send(json.dumps({"type":"task.action", "version":1, "task_id":"t1",
                                          "request_id":"p1", "action":"approve"}))
                await ws.close()
        finally:
            listener.close()
            await listener.wait_closed()
        assert calls == []
    asyncio.run(scenario())
