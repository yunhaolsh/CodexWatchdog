import asyncio

from daemon.protocol import TaskAction, TaskStatus
from daemon.ws_server import StackChanWebSocketServer, decode_hello


class FakeWebSocket:
    def __init__(self, incoming):
        self.incoming = incoming
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.incoming:
            raise StopAsyncIteration
        return self.incoming.pop(0)

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self, **_kwargs):
        self.closed = True


def test_server_replays_latest_status_and_forwards_action():
    async def scenario():
        actions = []
        server = StackChanWebSocketServer(actions.append)
        await server.publish(TaskStatus("t1", "running", title="Working", sequence=1))
        ws = FakeWebSocket([
            '{"type":"hello","device_id":"stackchan-1"}',
            '{"version":1,"type":"task.action","task_id":"t1","action":"approve"}',
        ])
        await server.handle(ws, "/stackChan/ws?deviceType=StackChan")
        assert actions and isinstance(actions[0], TaskAction)
        assert '"state":"running"' in ws.sent[0]

    asyncio.run(scenario())


def test_decode_hello_rejects_other_messages():
    try:
        decode_hello('{"type":"status"}')
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid hello to fail")
