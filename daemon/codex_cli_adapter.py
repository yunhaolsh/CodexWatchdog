"""Codex exec JSONL monitoring; interactive approvals require another backend."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path


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
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    if kind in {"thread.started", "turn.started"}:
        return CodexEvent(task_id, "running", "analysis", "Working / 执行中")
    if kind in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item")
        if not isinstance(item, dict):
            return None
        item_type = item.get("type")
        if item_type == "command_execution":
            return CodexEvent(task_id, "running", "command", "Command / 执行命令", str(item.get("command", ""))[:500])
        if item_type == "agent_message":
            return CodexEvent(task_id, "running", "response", "Response / 回复", str(item.get("text", ""))[:500])
        if item_type == "file_change":
            return CodexEvent(task_id, "running", "edit", "Editing / 修改文件")
    if kind == "turn.completed":
        return CodexEvent(task_id, "success", "complete", "Completed / 本轮完成")
    if kind in {"turn.failed", "error"}:
        error = event.get("error", {})
        message = error.get("message", "") if isinstance(error, dict) else str(error)
        return CodexEvent(task_id, "failed", "error", "Failed / 执行失败", str(event.get("message", message))[:500])
    return None


class CodexCliAdapter:
    def __init__(self, executable: str = "codex"):
        self.executable = executable

    async def run(self, prompt: str, cwd: str | Path | None = None,
                  extra_args: Sequence[str] = (), task_id: str | None = None) -> AsyncIterator[CodexEvent]:
        task_id = task_id or uuid.uuid4().hex
        yield CodexEvent(task_id, "running", "starting", "Starting / 启动中")
        process = await asyncio.create_subprocess_exec(
            self.executable, "exec", "--json", *extra_args, "--", prompt,
            cwd=str(cwd) if cwd else None, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=4 * 1024 * 1024, start_new_session=(os.name == "posix"),
        )

        async def drain_stderr():
            # Consume diagnostics without persisting secrets or mixing them into JSONL.
            while await process.stderr.read(8192):
                pass

        stderr_task = asyncio.create_task(drain_stderr())
        terminal = None
        try:
            async for raw in process.stdout:
                event = parse_json_event(raw.decode(errors="replace"), task_id)
                if event is not None:
                    if event.state in {"success", "failed"}:
                        if terminal is None or event.state == "failed":
                            terminal = event
                    else:
                        yield event
            return_code = await process.wait()
            await stderr_task
            if return_code:
                yield CodexEvent(task_id, "failed", "error", "Failed / 执行失败", f"Codex exit code {return_code}")
            elif terminal is not None:
                yield terminal
            else:
                yield CodexEvent(task_id, "failed", "error", "Incomplete / 状态不完整", "Codex exited without turn.completed")
        finally:
            if process.returncode is None:
                try:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGTERM)
                    else:
                        process.terminate()
                    await asyncio.wait_for(process.wait(), 3)
                except TimeoutError:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    await process.wait()
                except ProcessLookupError:
                    await process.wait()
            stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)
