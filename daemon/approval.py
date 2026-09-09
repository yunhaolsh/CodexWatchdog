"""Normalize app-server approval requests and build exact RPC responses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalRequest:
    rpc_id: int | str
    kind: str
    item_id: str
    command: str
    cwd: str
    reason: str
    available_decisions: tuple[Any, ...]

    @classmethod
    def from_rpc(cls, message: dict[str, Any]) -> "ApprovalRequest" | None:
        method = message.get("method")
        if method not in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            return None
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(message.get("id"), (str, int)):
            raise ValueError("malformed approval request")
        item_id = params.get("itemId")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("approval itemId is required")
        decisions = params.get("availableDecisions")
        return cls(
            rpc_id=message["id"],
            kind="command" if "commandExecution" in method else "file_change",
            item_id=item_id,
            command=str(params.get("command") or ""),
            cwd=str(params.get("cwd") or ""),
            reason=str(params.get("reason") or ""),
            available_decisions=tuple(decisions) if isinstance(decisions, list) else (),
        )

    def response(self, decision: str) -> dict[str, Any]:
        if self.kind == "command":
            if decision not in {"accept", "acceptForSession", "decline", "cancel"}:
                raise ValueError("unsupported command decision")
            return {"jsonrpc": "2.0", "id": self.rpc_id, "result": {"decision": decision}}
        if decision not in {"accept", "decline", "cancel"}:
            raise ValueError("unsupported file change decision")
        return {"jsonrpc": "2.0", "id": self.rpc_id, "result": {"decision": decision}}
