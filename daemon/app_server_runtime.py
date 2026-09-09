"""Run one Codex turn through app-server and bridge its approvals."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from .app_server import CodexAppServer
from .codex_cli_adapter import CodexEvent
from .protocol import TaskAction


def notification_event(message: dict[str, Any], task_id: str) -> CodexEvent | None:
    method = message.get("method")
    params = message.get("params") or {}
    item = params.get("item") or {}
    item_type = item.get("type")
    if method == "item/started" and item_type == "commandExecution":
        return CodexEvent(task_id, "running", "command", "Command / 执行命令", str(item.get("command") or "")[:500])
    if method in {"item/agentMessage/delta", "item/completed"} and item_type == "agentMessage":
        return CodexEvent(task_id, "running", "response", "Response / 回复", str(item.get("text") or "")[:500])
    if method == "item/completed" and item_type == "commandExecution":
        return CodexEvent(task_id, "running", "command", "Command done / 命令完成")
    if method in {"turn/completed", "turn/completed/notification"}:
        return CodexEvent(task_id, "success", "complete", "Completed / 本轮完成")
    if method in {"turn/failed", "error"}:
        return CodexEvent(task_id, "failed", "error", "Failed / 执行失败", str(params.get("message") or ""))
    return None


class AppServerTaskAdapter:
    """Adapter with a device-facing approval broker.

    The app-server reader remains alive while a request is waiting: the future
    is completed by ``handle_action`` from the StackChan WebSocket task.
    """

    def __init__(self, executable: str = "codex", event_handler=None):
        self.event_handler = event_handler
        self.client = CodexAppServer(executable, approval_handler=self._approval)
        self.client.notification_handler = self._notification
        self._events: asyncio.Queue[CodexEvent] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[str]] = {}
        self._task_id = ""
        self._thread_id = ""

    async def _notification(self, message: dict[str, Any]) -> None:
        event = notification_event(message, self._task_id)
        if event is not None:
            await self._events.put(event)
            if self.event_handler is not None:
                result = self.event_handler(event)
                if asyncio.iscoroutine(result):
                    await result

    async def _approval(self, request) -> str:
        request_id = str(request.rpc_id)
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._events.put(CodexEvent(
            self._task_id, "waiting", "permission", "Approval required / 需要确认",
            request.command or request.reason or "File change / 文件变更", request_id, True,
        ))
        try:
            return await asyncio.wait_for(future, 300)
        except TimeoutError:
            return "cancel"
        finally:
            self._pending.pop(request_id, None)

    async def run(self, prompt: str, cwd: str | Path, task_id: str | None = None):
        self._task_id = task_id or uuid.uuid4().hex
        try:
            await self.client.start()
            thread = await self.client.request("thread/start", {
                "cwd": str(Path(cwd).resolve()), "approvalPolicy": "on-request",
                "experimentalRawEvents": False,
            })
            self._thread_id = (thread.get("thread") or {}).get("id") or thread.get("threadId", "")
            if not self._thread_id:
                raise RuntimeError("app-server thread/start returned no thread id")
            await self.client.request("turn/start", {
                "threadId": self._thread_id, "input": [{"type": "text", "text": prompt}],
                "cwd": str(Path(cwd).resolve()), "approvalPolicy": "on-request",
            })
            while True:
                event = await asyncio.wait_for(self._events.get(), 600)
                yield event
                if event.state in {"success", "failed"}:
                    break
        finally:
            await self.client.close()

    async def handle_action(self, action: TaskAction) -> dict[str, Any]:
        future = self._pending.get(action.request_id or "")
        if action.task_id != self._task_id or future is None or future.done():
            return {"accepted": False, "code": "stale_or_unknown_request"}
        future.set_result("accept" if action.action == "approve" else "decline")
        return {"accepted": True, "code": "forwarded"}
