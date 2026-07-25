"""Unit tests for the F11/F14 approval seam (S3)."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn_agents.approval_hook import ApprovalHook, authorize_tool_call
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_permissions import ToolPermissions


class _RecordingHook(ApprovalHook):
    """Approval hook that records requests and returns a scripted decision."""

    def __init__(self, decision: bool) -> None:
        self._decision = decision
        self.requests: list[tuple[str, Mapping[str, Any]]] = []

    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        self.requests.append((tool_name, dict(arguments)))
        return self._decision


class TestApprovalHookDefault(unittest.IsolatedAsyncioTestCase):
    async def test_base_hook_auto_approves(self) -> None:
        hook = ApprovalHook()
        assert await hook.request_approval(tool_name="t", arguments={}) is True


class TestAuthorizeToolCall(unittest.IsolatedAsyncioTestCase):
    async def test_unrestricted_tool_bypasses_hook(self) -> None:
        stub = StubTool(name="reader")
        hook = _RecordingHook(decision=False)
        # No approval required, so the (denying) hook is never consulted.
        assert await authorize_tool_call(stub, {"input": "x"}, hook) is True
        assert hook.requests == []

    async def test_gated_tool_routes_through_hook_and_approves(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        hook = _RecordingHook(decision=True)
        assert await authorize_tool_call(stub, {"input": "x"}, hook) is True
        assert hook.requests == [("danger", {"input": "x"})]

    async def test_gated_tool_routes_through_hook_and_denies(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        hook = _RecordingHook(decision=False)
        assert await authorize_tool_call(stub, {"input": "x"}, hook) is False
        assert hook.requests == [("danger", {"input": "x"})]

    async def test_gated_tool_without_hook_auto_approves(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        # Inert by default: no hook wired means the forward seam auto-approves.
        assert await authorize_tool_call(stub, {"input": "x"}) is True


if __name__ == "__main__":
    unittest.main()
