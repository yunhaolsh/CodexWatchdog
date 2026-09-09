import asyncio

from daemon.protocol import TaskStatus
from daemon.stackchan_client import StackChanClient


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.incoming = asyncio.Queue()
        self.closed = False

    async def send_json(self, payload):
        self.sent.append(payload)

    async def recv_json(self):
        return await self.incoming.get()

    async def close(self):
        self.closed = True


def test_status_replayed_after_connect_and_actions_forwarded():
    async def scenario():
        transport = FakeTransport()
        client = StackChanClient(lambda: asyncio.sleep(0, result=transport))
        received = []
        client.set_action_handler(received.append)
        await client.publish(TaskStatus(task_id="t1", state="running", title="执行中"))
        await client.connect()
        assert transport.sent[0]["task_id"] == "t1"
        await transport.incoming.put({"version": 1, "type": "task.action", "task_id": "t1", "action": "approve"})
        action = await client.receive_once()
        assert action.action == "approve" and received == [action]

    asyncio.run(scenario())
