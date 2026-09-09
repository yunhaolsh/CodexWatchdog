import pytest

from daemon.device_session import DeviceSession
from daemon.protocol import TaskStatus


def test_hello_and_action_are_decoded():
    session = DeviceSession()
    assert session.receive_text('{"type":"hello","device_id":"stackchan-1"}') is None
    assert session.hello_received and session.device_id == "stackchan-1"
    action = session.receive_text('{"version":1,"type":"task.action","task_id":"t1","request_id":"p1","action":"approve"}')
    assert action and action.action == "approve"


def test_status_sequence_cannot_go_backwards():
    session = DeviceSession()
    session.encode_status(TaskStatus("t1", "running", sequence=2))
    with pytest.raises(ValueError):
        session.encode_status(TaskStatus("t1", "idle", sequence=1))
