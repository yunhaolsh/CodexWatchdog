from daemon.codex_cli_adapter import parse_json_event


def test_jsonl_events_are_normalized():
    started = parse_json_event('{"type":"turn.started"}', "t1")
    assert started and started.state == "running"
    command = parse_json_event('{"type":"item.started","item":{"type":"command_execution","command":"pytest"}}', "t1")
    assert command and command.message == "pytest"
    done = parse_json_event('{"type":"turn.completed"}', "t1")
    assert done and done.state == "success"


def test_unknown_or_non_json_output_is_ignored():
    assert parse_json_event("plain stderr", "t1") is None
    assert parse_json_event('{"type":"future.event"}', "t1") is None
    assert parse_json_event('[]', "t1") is None
    assert parse_json_event('{"type":"approval_required","id":"p1"}', "t1") is None
