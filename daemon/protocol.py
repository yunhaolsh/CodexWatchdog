"""Versioned messages exchanged with StackChan."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class TaskStatus:
    task_id: str
    state: str
    phase: str = ""
    title: str = ""
    message: str = ""
    request_id: str | None = None
    requires_action: bool = False
    sequence: int = 0
    version: int = 1
    type: str = "task.status"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

@dataclass(frozen=True)
class TaskAction:
    task_id: str
    action: str
    request_id: str | None = None
    version: int = 1
    type: str = "task.action"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskAction":
        if value.get("version") != 1 or value.get("type") != "task.action":
            raise ValueError("unsupported task action")
        if value.get("action") not in {"approve", "reject"}:
            raise ValueError("action must be approve or reject")
        task_id = value.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id is required")
        return cls(task_id=task_id, action=value["action"], request_id=value.get("request_id"))
