import asyncio
from types import SimpleNamespace

from daemon.app_server import CodexAppServer


def test_notification_handler_receives_non_approval_server_events():
    async def scenario():
        received = []
        client = CodexAppServer(notification_handler=received.append)
        client.process = SimpleNamespace()
        # Exercise the same dispatch branch without starting a provider process.
        approval = {"jsonrpc": "2.0", "id": 3, "method": "item/started", "params": {"item": {"type": "commandExecution"}}}
        parsed = __import__("json").dumps(approval).encode()

        class Stream:
            def __aiter__(self): return self
            async def __anext__(self):
                if self.done: raise StopAsyncIteration
                self.done = True
                return parsed
            done = False

        client.process.stdout = Stream()
        await client._read_loop()
        assert received == [approval]

    asyncio.run(scenario())
