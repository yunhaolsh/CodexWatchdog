"""Own one active task and publish snapshots on the daemon's event loop."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from .codex_cli_adapter import CodexCliAdapter
from .protocol import TaskAction
from .task_state import TaskState


class BusyError(Exception):
    pass


class TaskRuntime:
    def __init__(self, codex: CodexCliAdapter, stackchan):
        self.codex = codex
        self.stackchan = stackchan
        self.state = TaskState()
        self.tasks: dict[str, dict] = {}
        self._active: asyncio.Task | None = None
        self.stackchan.set_action_handler(self.handle_action)

    @property
    def busy(self) -> bool:
        return self._active is not None and not self._active.done()

    def submit(self, prompt: str, cwd: str) -> str:
        if self.busy:
            raise BusyError("another task is running")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
            raise ValueError("prompt must contain 1-16000 characters")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
            raise ValueError("cwd must be an existing absolute directory")
        task_id = uuid.uuid4().hex
        status = self.state.update(state="running", task_id=task_id, phase="starting", title="Starting / 启动中")
        self.tasks[task_id] = status.to_dict()
        while len(self.tasks) > 100:
            del self.tasks[next(iter(self.tasks))]
        self._active = asyncio.create_task(self._run(prompt, cwd, task_id))
        return task_id

    async def _publish(self, **fields):
        status = self.state.update(**fields)
        self.tasks[status.task_id] = status.to_dict()
        await self.stackchan.publish(status)

    async def _run(self, prompt: str, cwd: str, task_id: str) -> None:
        try:
            async for event in self.codex.run(prompt, cwd=cwd, task_id=task_id):
                await self._publish(
                    state=event.state, task_id=task_id, phase=event.phase,
                    title=event.title, message=event.message,
                    request_id=event.request_id, requires_action=event.requires_action,
                )
        except asyncio.CancelledError:
            await self._publish(state="failed", task_id=task_id, phase="cancelled", title="Stopped / 已停止")
            raise
        except Exception as exc:
            await self._publish(state="failed", task_id=task_id, phase="error", title="Failed / 执行失败", message=f"Codex backend failed: {type(exc).__name__}")

    async def cancel(self, task_id: str) -> bool:
        if not self.busy or self.state.task_id != task_id:
            return False
        self._active.cancel()
        await asyncio.gather(self._active, return_exceptions=True)
        if self.state.phase != "cancelled":
            # A task cancelled before its coroutine starts never enters _run's handler.
            await self._publish(state="failed", task_id=task_id, phase="cancelled", title="Stopped / 已停止")
        return True

    async def close(self) -> None:
        if self.busy:
            await self.cancel(self.state.task_id)

    async def handle_action(self, action: TaskAction) -> dict:
        # exec JSONL is monitoring-only. Never acknowledge an approval we cannot deliver.
        return {"accepted": False, "code": "approval_unavailable"}
