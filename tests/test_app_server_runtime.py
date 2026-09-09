from daemon.app_server_runtime import notification_event


def test_app_server_notifications_map_to_device_events():
    event = notification_event({"method": "item/started", "params": {"item": {"type": "commandExecution", "command": "pytest"}}}, "t1")
    assert event and event.phase == "command" and event.message == "pytest"
    done = notification_event({"method": "turn/completed", "params": {}}, "t1")
    assert done and done.state == "success"
