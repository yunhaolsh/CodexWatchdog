import pytest

from daemon.approval import ApprovalRequest


def test_command_approval_request_and_response():
    request = ApprovalRequest.from_rpc({
        "jsonrpc": "2.0", "id": 12,
        "method": "item/commandExecution/requestApproval",
        "params": {"itemId": "item-1", "command": "pytest", "cwd": "/tmp", "availableDecisions": ["accept", "decline"]},
    })
    assert request and request.kind == "command" and request.command == "pytest"
    assert request.response("accept") == {"jsonrpc": "2.0", "id": 12, "result": {"decision": "accept"}}
    with pytest.raises(ValueError):
        request.response("allow")


def test_unrelated_rpc_is_not_approval():
    assert ApprovalRequest.from_rpc({"id": 1, "method": "turn/started", "params": {}}) is None
