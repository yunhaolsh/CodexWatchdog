"""Minimal stdio JSON-RPC client for the Codex app-server protocol v2."""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .approval import ApprovalRequest


class AppServerError(RuntimeError):
    pass


class CodexAppServer:
    def __init__(self, executable: str = "codex", approval_handler: Callable[[ApprovalRequest], Awaitable[str] | str] | None = None):
        self.executable = executable
        self.approval_handler = approval_handler
        self.process = None
        self._reader_task = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0

    async def start(self) -> dict[str, Any]:
        self.process = await asyncio.create_subprocess_exec(
            self.executable, "app-server", "--stdio", stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        result = await self.request("initialize", {"clientInfo": {"name": "codexwatchdog", "title": "CodexWatchdog", "version": "0.1.0"}})
        await self.notify("initialized", {})
        return result

    async def _write(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise AppServerError("app-server is not started")
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        self._next_id += 1
        request_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            return await asyncio.wait_for(future, 30)
        finally:
            self._pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _read_loop(self) -> None:
        assert self.process and self.process.stdout
        try:
            async for raw in self.process.stdout:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "id" in message and message.get("id") in self._pending:
                    future = self._pending[message["id"]]
                    if "error" in message:
                        future.set_exception(AppServerError(str(message["error"])))
                    else:
                        future.set_result(message.get("result"))
                    continue
                approval = ApprovalRequest.from_rpc(message)
                if approval is not None:
                    await self._handle_approval(approval)
        except (ConnectionError, BrokenPipeError):
            pass
        finally:
            error = AppServerError("app-server closed")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)

    async def _handle_approval(self, request: ApprovalRequest) -> None:
        decision = "decline"
        if self.approval_handler is not None:
            decision = self.approval_handler(request)
            if asyncio.iscoroutine(decision):
                decision = await decision
        await self._write(request.response(str(decision)))

    async def close(self) -> None:
        if self.process is None:
            return
        if self.process.stdin:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 3)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        self.process = None
