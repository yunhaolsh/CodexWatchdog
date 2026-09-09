"""Transport-independent StackChan status publisher.

The real WebSocket transport can be plugged into ``send_json``/``recv_json``;
this module keeps state replay and action validation independent of that library.
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .protocol import TaskAction, TaskStatus


class JsonTransport(Protocol):
    async def send_json(self, payload: dict[str, Any]) -> None: ...
    async def recv_json(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class StackChanClient:
    def __init__(self, transport_factory: Callable[[], Awaitable[JsonTransport]]):
        self._transport_factory = transport_factory
        self._transport: JsonTransport | None = None
        self._last_status: TaskStatus | None = None
        self._action_handler: Callable[[TaskAction], Awaitable[None] | None] | None = None

    def set_action_handler(self, handler: Callable[[TaskAction], Awaitable[None] | None]) -> None:
        self._action_handler = handler

    async def publish(self, status: TaskStatus) -> None:
        self._last_status = status
        if self._transport is not None:
            await self._transport.send_json(status.to_dict())

    async def connect(self) -> None:
        self._transport = await self._transport_factory()
        if self._last_status is not None:
            await self._transport.send_json(self._last_status.to_dict())

    async def receive_once(self) -> TaskAction:
        if self._transport is None:
            raise RuntimeError("StackChan is not connected")
        action = TaskAction.from_dict(await self._transport.recv_json())
        if self._action_handler is not None:
            result = self._action_handler(action)
            if inspect.isawaitable(result):
                await result
        return action

    async def run(self, stop: asyncio.Event, retry_delay: float = 1.0) -> None:
        while not stop.is_set():
            try:
                await self.connect()
                while not stop.is_set():
                    await self.receive_once()
            except (OSError, asyncio.TimeoutError, ConnectionError):
                self._transport = None
                await asyncio.sleep(retry_delay)
            finally:
                if self._transport is not None:
                    await self._transport.close()
                    self._transport = None
