# CodexWatchdog

PC-side bridge for showing Codex CLI activity on a paired StackChan device.

The implementation roadmap is in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).

## Phase 1 local smoke test

```bash
python -m daemon.server
curl http://127.0.0.1:12880/health
curl -X POST http://127.0.0.1:12880/events -H 'Content-Type: application/json' -d '{"state":"running","task_id":"demo","phase":"analysis","title":"分析中"}'
curl http://127.0.0.1:12880/status
```

Install runtime dependencies with `python -m pip install -e .`.

Run tests with `python -m pytest`.

## Daemon entry points

```bash
python -m daemon.app serve --host 0.0.0.0 --port 12800
python -m daemon.app run "检查当前测试并修复失败项" --cwd /path/to/project
```

The StackChan firmware currently connects to `/stackChan/ws?deviceType=StackChan`.
