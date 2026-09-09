import asyncio

from daemon.codex_cli_adapter import CodexEvent
from daemon.runtime import TaskRuntime


class FakeCodex:
    async def run(self, *_args, **_kwargs):
        for event in [CodexEvent("t1", "running", title="Working"), CodexEvent("t1", "success", title="Done")]:
            yield event


class FakeStackChan:
    def __init__(self):
        self.published = []
        self.handler = None

    def set_action_handler(self, handler):
        self.handler = handler

    async def publish(self, status):
        self.published.append(status)


def test_runtime_publishes_codex_lifecycle():
    async def scenario():
        device = FakeStackChan()
        runtime = TaskRuntime(FakeCodex(), device)
        assert await runtime.run("test") == "t1"
        assert [item.state for item in device.published] == ["running", "success"]

    asyncio.run(scenario())
