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

Run tests with `python -m pytest`.
