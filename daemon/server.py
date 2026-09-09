"""Small local HTTP API for exercising the Phase 1 state machine."""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .task_state import TaskState

class WatchdogHandler(BaseHTTPRequestHandler):
    state = TaskState()
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health": self._send(200, {"ok": True, "service": "codexwatchdog"})
        elif self.path == "/status": self._send(200, self.state.snapshot().to_dict())
        else: self._send(404, {"error": "not found"})
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/events": self._send(404, {"error": "not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0")); event = json.loads(self.rfile.read(length)); status = self.state.update(**event)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)}); return
        self._send(200, status.to_dict())
    def log_message(self, *_args) -> None: return

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=12880); args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WatchdogHandler); print(f"CodexWatchdog listening on http://{args.host}:{args.port}"); server.serve_forever()

if __name__ == "__main__": main()
