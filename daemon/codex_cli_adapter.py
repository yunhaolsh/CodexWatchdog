"""Codex CLI adapter using the supported non-interactive JSONL mode."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexEvent:
    task_id: str
    state: str
    phase: str = ""
    title: str = ""
    message: str = ""
    request_id: str | None = None
    requires_action: bool = False


def parse_json_event(line: str, task_id: str) -> CodexEvent | None:
    """Map a Codex JSONL event to our small device-facing vocabulary.

    Unknown events are intentionally ignored; the raw CLI stream remains
    available to callers for diagnostics and future event mappings.
    """
    try:
        event: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError:
        return None
    kind = str(event.get("type", ""))
    if kind in {"thread.started", "turn.started"}:
        return CodexEvent(task_id, "running", "analysis", "Working / 执行中")
    if kind in {"item.started", "command.started"}:
        return CodexEvent(task_id, "running", "command", "Command / 执行命令", str(event.get("command", "")))
    if kind in {"approval_required", "permission.requested"}:
        request_id = event.get("request_id") or event.get("id")
        return CodexEvent(task_id, "waiting", "permission", "Approval required / 需要确认", str(event.get("message", event.get("command", ""))), str(request_id), True)
    if kind in {"turn.completed", "thread.completed"}:
        return CodexEvent(task_id, "success", "complete", "Completed / 已完成")
    if kind in {"turn.failed", "thread.failed", "error"}:
        return CodexEvent(task_id, "failed", "error", "Failed / 执行失败", str(event.get("message", event.get("error", ""))))
    return None


class CodexCliAdapter:
    def __init__(self, executable: str = "codex"):
        self.executable = executable

    async def run(self, prompt: str, cwd: str | Path | None = None, extra_args: Sequence[str] = ()) -> AsyncIterator[CodexEvent]:
        task_id = uuid.uuid4().hex[:12]
        process = await asyncio.create_subprocess_exec(
            self.executable, "exec", "--json", *extra_args, prompt,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            event = parse_json_event(line, task_id)
            if event is not None:
                yield event
        return_code = await process.wait()
        if return_code:
            yield CodexEvent(task_id, "failed", "error", "Failed / 执行失败", f"exit code {return_code}")
