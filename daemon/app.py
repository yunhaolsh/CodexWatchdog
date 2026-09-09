"""One daemon process owns the HTTP API, task runtime, and device endpoint."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .codex_cli_adapter import CodexCliAdapter
from .app_server_runtime import AppServerTaskAdapter
from .runtime import BusyError, TaskRuntime
from .server import ControlServer
from .ws_server import StackChanWebSocketServer


class App:
    def __init__(self, runtime, device_server):
        self.runtime = runtime
        self.device_server = device_server
        self.http = None
        self.ws = None

    async def start(self, host="127.0.0.1", port=12800, api_port=12880):
        self.ws = await self.device_server.serve(host, port)
        try:
            self.http = ControlServer(self.dispatch, self.device_server.token, api_port)
        except BaseException:
            self.ws.close()
            await self.ws.wait_closed()
            raise

    async def close(self):
        if self.http:
            await self.http.close()
        await self.runtime.close()
        if self.ws:
            self.ws.close()
            await self.ws.wait_closed()

    async def dispatch(self, method, path, payload):
        if method == "GET" and path == "/health":
            return 200, {"ok": True, "device_connected": self.device_server.connected,
                         "busy": self.runtime.busy, "approval_supported": False}
        if method == "GET" and path == "/status":
            return 200, self.runtime.state.snapshot().to_dict()
        if method == "GET" and path.startswith("/tasks/"):
            status = self.runtime.tasks.get(path.removeprefix("/tasks/"))
            return (200, status) if status else (404, {"error": "unknown task"})
        if method == "POST" and path == "/tasks":
            try:
                if set(payload) != {"prompt", "cwd"}:
                    raise ValueError("expected prompt and cwd")
                task_id = self.runtime.submit(payload["prompt"], payload["cwd"])
                return 202, {"task_id": task_id}
            except BusyError as exc:
                return 409, {"error": str(exc)}
            except ValueError as exc:
                return 400, {"error": str(exc)}
        if method == "POST" and path.startswith("/tasks/") and path.endswith("/cancel"):
            task_id = path[len("/tasks/"):-len("/cancel")]
            if await self.runtime.cancel(task_id):
                return 200, self.runtime.tasks[task_id]
            return 409, {"error": "task is not running"}
        return 404, {"error": "not found"}


def create_app(codex_executable="codex", *, token: str, device_id="stackchan-1", backend="exec") -> App:
    device_server = StackChanWebSocketServer(token, device_id)
    codex = AppServerTaskAdapter(codex_executable) if backend == "app-server" else CodexCliAdapter(codex_executable)
    return App(TaskRuntime(codex, device_server), device_server)


def load_token(path: Path, create=False) -> str:
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as target:
                target.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    token = path.read_text().strip()
    if len(token) < 32:
        raise ValueError("token file must contain at least 32 characters")
    return token


def api_request(port, token, method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}: {exc.read().decode()}") from exc


def main():
    parser = argparse.ArgumentParser(prog="codexwatchdog")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "run", "status", "cancel", "simulate-device"):
        child = sub.add_parser(name)
        child.add_argument("--token-file", type=Path, default=Path(".run/token"))
        child.add_argument("--api-port", type=int, default=12880)
        if name == "serve":
            child.add_argument("--host", default="127.0.0.1")
            child.add_argument("--port", type=int, default=12800)
            child.add_argument("--device-id", default="stackchan-1")
            child.add_argument("--codex", default="codex")
            child.add_argument("--backend", choices=("exec", "app-server"), default="exec")
        elif name == "run":
            child.add_argument("prompt")
            child.add_argument("--cwd", type=Path, default=Path.cwd())
            child.add_argument("--wait", action="store_true")
        elif name == "cancel":
            child.add_argument("task_id")
        elif name == "simulate-device":
            child.add_argument("--url", default="ws://127.0.0.1:12800/stackChan/ws")
            child.add_argument("--device-id", default="stackchan-1")
    args = parser.parse_args()
    try:
        token = load_token(args.token_file, create=args.command == "serve")
        if args.command == "serve":
            async def serve_forever():
                app = create_app(args.codex, token=token, device_id=args.device_id, backend=args.backend)
                await app.start(args.host, args.port, args.api_port)
                stop = asyncio.Event()
                loop = asyncio.get_running_loop()
                for signum in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(signum, stop.set)
                print(json.dumps({"http": f"http://127.0.0.1:{app.http.port}",
                                  "websocket": f"ws://{args.host}:{args.port}/stackChan/ws"}), flush=True)
                try:
                    await stop.wait()
                finally:
                    await app.close()
            asyncio.run(serve_forever())
        elif args.command == "simulate-device":
            from .simulator import monitor
            asyncio.run(monitor(args.url, token, args.device_id))
        elif args.command == "status":
            print(json.dumps(api_request(args.api_port, token, "GET", "/status"), ensure_ascii=False))
        elif args.command == "cancel":
            print(json.dumps(api_request(args.api_port, token, "POST", f"/tasks/{args.task_id}/cancel", {}), ensure_ascii=False))
        else:
            result = api_request(args.api_port, token, "POST", "/tasks", {"prompt": args.prompt, "cwd": str(args.cwd.resolve())})
            print(json.dumps(result), flush=True)
            if args.wait:
                last_sequence = -1
                while True:
                    status = api_request(args.api_port, token, "GET", f"/tasks/{result['task_id']}")
                    if status["sequence"] != last_sequence:
                        print(json.dumps(status, ensure_ascii=False), flush=True)
                        last_sequence = status["sequence"]
                    if status["state"] in {"success", "failed"}:
                        return 0 if status["state"] == "success" else 1
                    time.sleep(0.3)
    except (OSError, URLError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
