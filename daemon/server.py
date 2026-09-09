"""Loopback HTTP control API; all state changes execute on the async loop."""
from __future__ import annotations

import asyncio
import json
import secrets
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ControlServer:
    def __init__(self, dispatch, token: str, port: int = 12880):
        loop = asyncio.get_running_loop()

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def reply(self, code, body):
                data = json.dumps(body, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def handle_request(self):
                auth = self.headers.get_all("Authorization") or []
                if len(auth) != 1 or not secrets.compare_digest(auth[0].encode(), f"Bearer {token}".encode()):
                    self.reply(401, {"error": "unauthorized"})
                    return
                if self.headers.get("Origin"):
                    self.reply(403, {"error": "browser requests are not supported"})
                    return
                payload = {}
                if self.command == "POST":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 65536 or self.headers.get("Transfer-Encoding"):
                            raise ValueError("invalid body size")
                        payload = json.loads(self.rfile.read(length))
                        if not isinstance(payload, dict):
                            raise ValueError("expected a JSON object")
                    except (ValueError, TimeoutError):
                        self.reply(400, {"error": "invalid JSON body"})
                        return
                future = asyncio.run_coroutine_threadsafe(dispatch(self.command, self.path, payload), loop)
                try:
                    code, body = future.result(timeout=10)
                except FutureTimeout:
                    future.cancel()
                    code, body = 504, {"error": "daemon timeout; query task state before retrying"}
                except Exception:
                    code, body = 500, {"error": "daemon request failed"}
                try:
                    self.reply(code, body)
                except OSError:
                    pass

            do_GET = handle_request
            do_POST = handle_request

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    async def close(self):
        await asyncio.to_thread(self.server.shutdown)
        self.server.server_close()
        await asyncio.to_thread(self.thread.join)


if __name__ == "__main__":
    raise SystemExit("Use python -m daemon.app serve to start HTTP and WebSocket together.")
