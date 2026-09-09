"""Application composition for the first usable PC daemon."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .codex_cli_adapter import CodexCliAdapter
from .runtime import TaskRuntime
from .ws_server import StackChanWebSocketServer


@dataclass
class App:
    runtime: TaskRuntime
    device_server: StackChanWebSocketServer


def create_app(codex_executable: str = "codex") -> App:
    device_server = StackChanWebSocketServer()
    runtime = TaskRuntime(CodexCliAdapter(codex_executable), device_server)
    return App(runtime, device_server)


async def run_task(app: App, prompt: str, cwd: str | None = None) -> None:
    await app.runtime.run(prompt, cwd)


def main() -> None:
    parser = argparse.ArgumentParser(prog="codexwatchdog")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="start the StackChan WebSocket endpoint")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=12800)
    run = sub.add_parser("run", help="run one Codex CLI task")
    run.add_argument("prompt")
    run.add_argument("--cwd")
    args = parser.parse_args()
    app = create_app()
    if args.command == "run":
        asyncio.run(run_task(app, args.prompt, args.cwd))
        return

    async def serve_forever() -> None:
        server = await app.device_server.serve(args.host, args.port)
        print(json.dumps({"ok": True, "endpoint": f"ws://{args.host}:{args.port}/stackChan/ws"}))
        await server.wait_closed()

    asyncio.run(serve_forever())


if __name__ == "__main__":
    main()
