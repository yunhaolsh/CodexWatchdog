"""Stateful protocol boundary for one connected StackChan device."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .protocol import TaskAction, TaskStatus


@dataclass
class DeviceSession:
    device_id: str = "unidentified"
    hello_received: bool = False
    last_sequence: int = 0

    def receive_text(self, raw: str) -> TaskAction | None:
        payload: dict[str, Any] = json.loads(raw)
        if payload.get("type") == "hello":
            self.hello_received = True
            self.device_id = str(payload.get("device_id") or payload.get("msg") or self.device_id)
            return None
        if payload.get("type") == "task.action":
            return TaskAction.from_dict(payload)
        return None

    def encode_status(self, status: TaskStatus) -> str:
        if status.sequence < self.last_sequence:
            raise ValueError("status sequence moved backwards")
        self.last_sequence = status.sequence
        return status.to_json()
