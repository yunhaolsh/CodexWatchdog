from daemon.app import create_app


def test_app_wires_runtime_to_device_server():
    app = create_app("fake-codex", token="test-token")
    assert app.runtime.codex.executable == "fake-codex"
    assert app.device_server._action_handler == app.runtime.handle_action
