from daemon.diagnostics import diagnose


def test_success_does_not_imply_device_connected():
    report = diagnose({"ok": True, "device_connected": False}, {"state": "success"})
    assert report["device_transport"] == "disconnected"
    assert report["screen"] == "unverified"
    assert report["task"]["state"] == "success"


def test_connection_does_not_imply_screen_verified():
    report = diagnose({"ok": True, "device_connected": True}, {"state": "idle"})
    assert report["device_transport"] == "connected"
    assert report["screen"] == "unverified"
