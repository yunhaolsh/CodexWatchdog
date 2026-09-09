"""Coordinate Codex events, task state, and device publication."""
from __future__ import annotations

from .codex_cli_adapter import CodexCliAdapter
from .stackchan_client import StackChanClient
from .task_state import TaskState


class TaskRuntime:
    def __init__(self, codex: CodexCliAdapter, stackchan: StackChanClient):
        self.codex = codex
        self.stackchan = stackchan
        self.state = TaskState()
        self.stackchan.set_action_handler(self.handle_action)

    async def run(self, prompt: str, cwd: str | None = None) -> str:
        task_id = ""
        async for event in self.codex.run(prompt, cwd=cwd):
            task_id = task_id or event.task_id
            status = self.state.update(
                state=event.state,
                task_id=event.task_id,
                phase=event.phase,
                title=event.title,
                message=event.message,
                request_id=event.request_id,
                requires_action=event.requires_action,
            )
            await self.stackchan.publish(status)
        return task_id

    async def handle_action(self, action) -> None:
        if not self.state.accept_action(action.task_id, action.request_id or "", action.action):
            return
        # The PTY/approval writer will be attached in Phase 3.
        self.state.update(
            state="running", task_id=action.task_id, phase="permission",
            title="Approved / 已批准" if action.action == "approve" else "Rejected / 已拒绝",
        )
