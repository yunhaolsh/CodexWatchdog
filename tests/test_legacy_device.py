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
    assert length == len(frame[5:])
    assert payload["name"] == "CodexWatchdog" and payload["content"] == "执行中 / Working"
    assert payload["watchdog"]["state"] == "running"
    assert payload["watchdog"]["type"] == "task.status"


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


def test_legacy_heartbeat_requires_application_pong_and_allows_reconnect(monkeypatch):
    from daemon import ws_server
    monkeypatch.setattr(ws_server, 'LEGACY_HEARTBEAT_INTERVAL', 0.01)
    monkeypatch.setattr(ws_server, 'LEGACY_PONG_TIMEOUT', 0.15)

    async def scenario():
        server = StackChanWebSocketServer('test-token', legacy_device=True)
        listener = await server.serve(port=0)
        url = f'ws://127.0.0.1:{listener.sockets[0].getsockname()[1]}/stackChan/ws'
        try:
            async with connect(url, proxy=None) as ws:
                await ws.send('{"type":"hello"}')
                assert (await ws.recv())[0] == 7
                for _ in range(3):
                    assert await asyncio.wait_for(ws.recv(), 1) == bytes.fromhex('10 00000000')
                    await ws.send(bytes.fromhex('11 00000000'))
                assert await asyncio.wait_for(ws.recv(), 1) == bytes.fromhex('10 00000000')
                # WebSocket control pong and malformed application pong cannot keep
                # a stalled firmware UI alive: only the exact application frame counts.
                await ws.pong()
                await ws.send(bytes.fromhex('11 00000001 00'))
                await asyncio.wait_for(ws.wait_closed(), 2)
                assert ws.close_code == 1011
            for _ in range(100):
                if not server.connected:
                    break
                await asyncio.sleep(0.01)
            assert not server.connected
            async with connect(url, proxy=None) as ws:
                await ws.send('{"type":"hello"}')
                assert (await ws.recv())[0] == 7
                assert await ws.recv() == bytes.fromhex('10 00000000')
                await ws.send(bytes.fromhex('11 00000000'))
        finally:
            listener.close()
            await listener.wait_closed()
    asyncio.run(scenario())


def test_completion_preserves_response_for_reconnect_but_not_next_task():
    async def scenario():
        server = StackChanWebSocketServer("test-token", legacy_device=True)
        await server.publish(TaskStatus("first", "running", phase="response", message="最终回复"))
        completed = TaskStatus("first", "success", title="Completed / 本轮完成")
        await server.publish(completed)
        snapshot = json.loads(server._encode_status(server._latest)[5:])
        assert snapshot["watchdog"]["message"] == "最终回复"
        assert snapshot["watchdog"]["state"] == "success"
        assert completed.message == ""  # immutable canonical status stays unchanged
        await server.publish(TaskStatus("second", "running"))
        await server.publish(TaskStatus("second", "success"))
        snapshot = json.loads(server._encode_status(server._latest)[5:])
        assert snapshot["watchdog"]["message"] == ""
    asyncio.run(scenario())
