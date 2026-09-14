"""Approval gating for :class:`ParallelToolExecutor` (PIR-865).

Kept in its own module rather than appended to ``test_parallel_tool_executor.py``:
that file is concurrently being edited for its concurrency settings (PIR-866),
and this feature is orthogonal to concurrency/timeout/retry.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.toolset import Toolset


class _DenyHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        return False


class TestParallelToolExecutorApproval(unittest.IsolatedAsyncioTestCase):
    async def test_approved_call_runs_normally(self) -> None:
        danger = StubTool(
            name="danger", permissions=ToolPermissions(approval_required=True), result="ran"
        )
        toolset = Toolset([danger])
        calls = [ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")]
        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=calls, toolset=toolset, approval_hook=None, _config=KnotConfig(id="pte")
            )
        run = await t.run(RunRequest())
        assert run.succeeded, run.exceptions
        results: tuple[ToolResult, ...] = run.outputs["pte"]
        assert results[0].status == "ok"
        assert results[0].result == "ran"

    async def test_denied_call_is_skipped_not_an_error(self) -> None:
        danger = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        toolset = Toolset([danger])
        calls = [ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")]
        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=calls,
                toolset=toolset,
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="pte"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded, run.exceptions
        results: tuple[ToolResult, ...] = run.outputs["pte"]
        assert results[0].status == "skipped"
        assert results[0].error == "call skipped: approval denied"
        assert danger.invocations == []

    async def test_a_denial_does_not_affect_sibling_calls(self) -> None:
        danger = StubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        plain = StubTool(name="plain", result="fine")
        toolset = Toolset([danger, plain])
        calls = [
            ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1"),
            ToolCall(tool_name="plain", arguments={"input": "y"}, call_id="c2"),
        ]
        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=calls,
                toolset=toolset,
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="pte"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded, run.exceptions
        results: tuple[ToolResult, ...] = run.outputs["pte"]
        assert results[0].status == "skipped"
        assert results[1].status == "ok"
        assert results[1].result == "fine"


if __name__ == "__main__":
    unittest.main()
