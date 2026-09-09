from daemon.app import create_app
from daemon.app import load_token


def test_app_wires_runtime_to_device_server():
    app = create_app("fake-codex", token="test-token")
    assert app.runtime.codex.executable == "fake-codex"
    assert app.device_server._action_handler == app.runtime.handle_action


def test_app_can_select_app_server_backend():
    app = create_app("fake-codex", token="test-token", backend="app-server")
    assert app.runtime.codex.__class__.__name__ == "AppServerTaskAdapter"


def test_load_token_creates_private_file(tmp_path):
    path = tmp_path / ".run" / "token"
    token = load_token(path, create=True)
    assert len(token) >= 32
    assert path.stat().st_mode & 0o777 == 0o600
    assert load_token(path) == token
