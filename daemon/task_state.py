"""Task state machine independent of Codex and transport implementations."""
from __future__ import annotations
from dataclasses import dataclass
from .protocol import TaskStatus

VALID_STATES = {"idle", "running", "waiting", "success", "failed", "offline"}

@dataclass
class TaskState:
    task_id: str = "none"
    state: str = "idle"
    phase: str = ""
    title: str = "Ready / 就绪"
    message: str = ""
    request_id: str | None = None
    requires_action: bool = False
    sequence: int = 0

    def update(self, *, state: str, task_id: str | None = None, phase: str = "", title: str = "", message: str = "", request_id: str | None = None, requires_action: bool = False) -> TaskStatus:
        if state not in VALID_STATES:
            raise ValueError(f"unsupported state: {state}")
        if state == "waiting" and not request_id:
            raise ValueError("waiting state requires request_id")
        if task_id is not None:
            self.task_id = task_id
        self.state, self.phase, self.title, self.message = state, phase, title, message
        self.request_id, self.requires_action = request_id, requires_action
        self.sequence += 1
        return self.snapshot()

    def snapshot(self) -> TaskStatus:
        return TaskStatus(self.task_id, self.state, self.phase, self.title, self.message, self.request_id, self.requires_action, self.sequence)

    def accept_action(self, task_id: str, request_id: str, action: str) -> bool:
        return self.state == "waiting" and self.requires_action and self.task_id == task_id and self.request_id == request_id and action in {"approve", "reject"}
