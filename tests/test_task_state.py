import pytest
from daemon.protocol import TaskAction
from daemon.task_state import TaskState

def test_status_sequence_and_permission_action():
    state = TaskState(); running = state.update(state="running", task_id="t1", phase="analysis", title="分析中")
    waiting = state.update(state="waiting", phase="permission", title="需要确认", message="npm test", request_id="p1", requires_action=True)
    assert running.sequence == 1 and waiting.sequence == 2
    assert state.accept_action("t1", "p1", "approve") and not state.accept_action("t1", "old", "approve")

def test_waiting_requires_request_id():
    with pytest.raises(ValueError): TaskState().update(state="waiting", task_id="t1")

def test_action_validation():
    action = TaskAction.from_dict({"version": 1, "type": "task.action", "task_id": "t1", "request_id": "p1", "action": "reject"})
    assert action.action == "reject"
    with pytest.raises(ValueError): TaskAction.from_dict({"version": 1, "type": "task.action", "task_id": "t1", "action": "ignore"})
