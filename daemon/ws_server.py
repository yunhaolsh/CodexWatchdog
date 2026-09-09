"""Authenticated single-device endpoint for Watchdog protocol v1."""
from __future__ import annotations

import asyncio
import inspect
import json
import secrets
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .protocol import TaskAction, TaskStatus


class StackChanWebSocketServer:
    def __init__(self, token: str, device_id: str = "stackchan-1"):
        if not token:
            raise ValueError("device token is required")
        self.token = token
        self.device_id = device_id
        self._connection: ServerConnection | None = None
        self._latest = TaskStatus("none", "idle", title="Ready / 就绪")
        self._action_handler = None
        self._send_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._connection is not None

    def set_action_handler(self, handler) -> None:
        self._action_handler = handler

    async def publish(self, status: TaskStatus) -> None:
        async with self._send_lock:
            self._latest = status
            connection = self._connection
            if connection is not None:
                try:
                    await asyncio.wait_for(connection.send(status.to_json()), 3)
                except (ConnectionClosed, TimeoutError):
                    self._connection = None
                    await connection.close()

    def _authenticate(self, connection, request):
        if urlsplit(request.path).path != "/stackChan/ws":
            return connection.respond(404, "unknown endpoint\n")
        values = request.headers.get_all("Authorization")
        expected = f"Bearer {self.token}".encode()
        if len(values) != 1 or not secrets.compare_digest(values[0].encode(), expected):
            return connection.respond(401, "unauthorized\n")
        if request.headers.get_all("Origin"):
            return connection.respond(403, "browser connections are not supported\n")
        return None

    async def handle(self, websocket: ServerConnection) -> None:
        try:
            raw = await asyncio.wait_for(websocket.recv(), 5)
            hello = decode_hello(raw)
            if hello["device_id"] != self.device_id:
                await websocket.close(1008, "device is not paired")
                return
            async with self._send_lock:
                if self._connection is not None:
                    await websocket.close(1008, "device already connected")
                    return
                self._connection = websocket
                await websocket.send(json.dumps({
                    "type": "hello", "version": 1, "device_id": self.device_id,
                    "capabilities": {"approval": False},
                }))
                await websocket.send(self._latest.to_json())
            async for raw in websocket:
                try:
                    if not isinstance(raw, str):
                        raise ValueError("expected a text message")
                    action = TaskAction.from_dict(json.loads(raw))
                except (ValueError, TypeError):
                    await websocket.send(json.dumps({"type": "error", "code": "invalid_action"}))
                    continue
                result = {"accepted": False, "code": "approval_unavailable"}
                if self._action_handler is not None:
                    result = self._action_handler(action)
                    if inspect.isawaitable(result):
                        result = await result
                await websocket.send(json.dumps({
                    "type": "task.action.result", "version": 1,
                    "task_id": action.task_id, "request_id": action.request_id, **result,
                }))
        except (ValueError, TypeError, TimeoutError):
            await websocket.close(1008, "invalid or missing hello")
        except ConnectionClosed:
            pass
        finally:
            if self._connection is websocket:
                self._connection = None

    async def serve(self, host: str = "127.0.0.1", port: int = 12800):
        return await serve(
            self.handle, host, port, process_request=self._authenticate,
            ping_interval=10, ping_timeout=10, close_timeout=2,
            max_size=16384, max_queue=16,
        )


def decode_hello(raw: str) -> dict:
    if not isinstance(raw, str):
        raise ValueError("expected a text hello")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("type") != "hello":
        raise ValueError("expected StackChan hello")
    if type(payload.get("version")) is not int or payload["version"] != 1:
        raise ValueError("unsupported protocol version")
    if not isinstance(payload.get("device_id"), str) or not payload["device_id"]:
        raise ValueError("device_id is required")
    return payload
