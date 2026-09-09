"""WebSocket server integration for the StackChan主动连接协议."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .device_session import DeviceSession
from .protocol import TaskAction, TaskStatus


class StackChanWebSocketServer:
    """Serve one paired device and fan out the latest task status."""

    def __init__(self, action_handler: Callable[[TaskAction], Awaitable[None] | None] | None = None):
        self.session = DeviceSession()
        self._connection: Any = None
        self._latest: TaskStatus | None = None
        self._action_handler = action_handler

    def set_action_handler(self, handler: Callable[[TaskAction], Awaitable[None] | None]) -> None:
        self._action_handler = handler

    async def publish(self, status: TaskStatus) -> None:
        self._latest = status
        if self._connection is not None:
            await self._connection.send(self.session.encode_status(status))

    async def handle(self, websocket: Any, path: str = "") -> None:
        if path and not path.startswith("/stackChan/ws"):
            await websocket.close(code=1008, reason="unsupported path")
            return
        self._connection = websocket
        try:
            async for raw in websocket:
                if not isinstance(raw, str):
                    continue
                action = self.session.receive_text(raw)
                if action is not None and self._action_handler is not None:
                    result = self._action_handler(action)
                    if asyncio.iscoroutine(result):
                        await result
                if self.session.hello_received and self._latest is not None:
                    await websocket.send(self.session.encode_status(self._latest))
                    self._latest = None
        finally:
            if self._connection is websocket:
                self._connection = None

    async def serve(self, host: str = "0.0.0.0", port: int = 12800) -> Any:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("install websockets to run the StackChan server") from exc
        return await websockets.serve(self.handle, host, port)


def decode_hello(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if payload.get("type") != "hello":
        raise ValueError("expected StackChan hello")
    return payload
