import asyncio
import pytest

from daemon.codex_cli_adapter import CodexEvent
from daemon.runtime import BusyError, TaskRuntime


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


def test_runtime_publishes_codex_lifecycle(tmp_path):
    async def scenario():
        device = FakeStackChan()
        runtime = TaskRuntime(FakeCodex(), device)
        task_id = runtime.submit("test", str(tmp_path))
        with pytest.raises(BusyError):
            runtime.submit("another", str(tmp_path))
        await runtime._active
        assert runtime.tasks[task_id]["state"] == "success"
        assert [item.state for item in device.published] == ["running", "success"]

    asyncio.run(scenario())


def test_immediate_cancel_and_approval_do_not_leave_false_state(tmp_path):
    from daemon.protocol import TaskAction

    async def scenario():
        device = FakeStackChan()
        runtime = TaskRuntime(FakeCodex(), device)
        task_id = runtime.submit("test", str(tmp_path))
        assert await runtime.cancel(task_id)
        assert runtime.state.phase == "cancelled"
        before = runtime.state.snapshot()
        result = await runtime.handle_action(TaskAction(task_id, "approve", "p1"))
        assert not result["accepted"]
        assert runtime.state.snapshot() == before

    asyncio.run(scenario())
