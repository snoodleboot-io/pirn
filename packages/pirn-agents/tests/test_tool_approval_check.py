"""Unit tests for :class:`ToolApprovalCheck` — the ``Check`` half of approval gating (PIR-865)."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.check import Check
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.agent.tool_approval_check import ToolApprovalCheck
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_permissions import ToolPermissions


class _RecordingHook(ApprovalHook):
    def __init__(self, decision: bool) -> None:
        self._decision = decision
        self.requests: list[tuple[str, Mapping[str, Any]]] = []

    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        self.requests.append((tool_name, dict(arguments)))
        return self._decision


class TestToolApprovalCheckIsAProperCheck(unittest.TestCase):
    def test_it_is_a_core_check(self) -> None:
        assert issubclass(ToolApprovalCheck, Check)

    def test_skip_reason_constant(self) -> None:
        assert ToolApprovalCheck.skip_reason == "approval_denied"


class TestToolApprovalCheckProcess(unittest.IsolatedAsyncioTestCase):
    """``process()`` evaluates the exact policy ``ApprovalHook.authorize`` implements."""

    async def test_unrestricted_tool_approves_without_consulting_hook(self) -> None:
        stub = StubTool(name="reader")
        hook = _RecordingHook(decision=False)
        check = ToolApprovalCheck(
            tool=stub, arguments={"input": "x"}, hook=hook, _config=KnotConfig(id="c")
        )
        assert await check.process(tool=stub, arguments={"input": "x"}, hook=hook) is True
        assert hook.requests == []

    async def test_gated_tool_approved_by_hook(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        hook = _RecordingHook(decision=True)
        check = ToolApprovalCheck(
            tool=stub, arguments={"input": "x"}, hook=hook, _config=KnotConfig(id="c")
        )
        assert await check.process(tool=stub, arguments={"input": "x"}, hook=hook) is True
        assert hook.requests == [("danger", {"input": "x"})]

    async def test_gated_tool_denied_by_hook(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        hook = _RecordingHook(decision=False)
        check = ToolApprovalCheck(
            tool=stub, arguments={"input": "x"}, hook=hook, _config=KnotConfig(id="c")
        )
        assert await check.process(tool=stub, arguments={"input": "x"}, hook=hook) is False

    async def test_gated_tool_without_hook_auto_approves(self) -> None:
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        check = ToolApprovalCheck(
            tool=stub, arguments={"input": "x"}, hook=None, _config=KnotConfig(id="c")
        )
        assert await check.process(tool=stub, arguments={"input": "x"}, hook=None) is True

    async def test_runs_as_an_ordinary_knot_through_the_engine(self) -> None:
        """``process()`` is not the only path -- a real run resolves ``arguments`` too."""
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        hook = _RecordingHook(decision=False)
        with Tapestry() as t:
            args = Parameter("args", dict, default={"input": "x"}, _config=KnotConfig(id="args"))
            ToolApprovalCheck(tool=stub, arguments=args, hook=hook, _config=KnotConfig(id="c"))
        result = await t.run(RunRequest())
        assert result.outputs["c"] is False


class TestADenialNamesItselfInLineage(unittest.IsolatedAsyncioTestCase):
    """Core records and propagates the check's ``skip_reason`` (PIR-872)."""

    async def test_the_gate_and_the_tool_knot_record_approval_denied(self) -> None:
        # Arrange
        stub = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        factory = ToolFactory.of(stub)
        call = ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            knot = factory.for_call(call, approval_hook=_RecordingHook(decision=False))

        # Act
        result = await t.run(RunRequest(), terminals=knot)

        # Assert
        reasons = {row.knot_id: row.skip_reason for row in result.lineage}
        assert reasons[knot.knot_id] == "approval_denied"
        assert reasons[f"{knot.knot_id}:approval-gate"] == "approval_denied"
        assert stub.invocations == []

    async def test_an_approved_call_records_no_skip(self) -> None:
        stub = StubTool(
            name="danger", permissions=ToolPermissions(approval_required=True), result="ran"
        )
        call = ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            knot = ToolFactory.of(stub).for_call(call, approval_hook=_RecordingHook(decision=True))
        result = await t.run(RunRequest(), terminals=knot)
        assert result.outputs[knot.knot_id] == "ran"
        assert all(row.skip_reason is None for row in result.lineage)


if __name__ == "__main__":
    unittest.main()
