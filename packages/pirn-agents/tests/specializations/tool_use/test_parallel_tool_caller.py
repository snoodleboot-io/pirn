"""Tests for :class:`ParallelToolCaller`.

``ParallelToolCaller`` is a ``SubTapestry`` since PIR-856: ``process`` returns
the sink of an inner pipeline (an ``Aggregator`` fanning out over one
``ToolInvocation`` per call) rather than the result itself, so the outcome
tests run a real tapestry and read the caller's output. That is the behaviour
under test — the whole point of the change is that every call goes through the
engine — and asserting on a directly-awaited ``process`` would no longer
exercise it. The input-validation tests still call ``process`` directly,
because the guards fire before any knot is built (see
``tests/specializations/planning/test_tool_executor.py`` for the identical
pattern PIR-733 established for the single-call case).
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.specializations.tool_use.parallel_tool_caller import (
    ParallelToolCaller,
)
from pirn_agents.testing.stub_tool import StubTool as KitStubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from tests.specializations.conftest import StubTool


class _DenyHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        return False


class TestParallelToolCallerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_all_tools_in_parallel(self) -> None:
        search = StubTool(name="search", handler="search-result")
        calc = StubTool(name="calc", handler="42")
        calls = [
            ToolCall(tool_name="search", arguments={"q": "news"}, call_id="c1"),
            ToolCall(tool_name="calc", arguments={"expr": "6*7"}, call_id="c2"),
        ]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[search, calc],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        assert len(results) == 2
        by_id = {r.call_id: r for r in results}
        assert by_id["c1"].result == "search-result"
        assert by_id["c2"].result == "42"
        assert by_id["c1"].error is None
        assert by_id["c2"].error is None

    async def test_returns_error_for_unknown_tool(self) -> None:
        calls = [
            ToolCall(tool_name="nonexistent", arguments={}, call_id="cx"),
        ]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[StubTool(name="other")],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        assert len(results) == 1
        assert results[0].error is not None
        assert "nonexistent" in results[0].error

    async def test_returns_error_on_tool_exception(self) -> None:
        def raise_error(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("tool failed")

        bad_tool = StubTool(name="bad", handler=raise_error)
        calls = [ToolCall(tool_name="bad", arguments={}, call_id="c3")]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[bad_tool],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        # PIR-856: the call now runs through ToolInvocation, which reports
        # "TypeName: message" (and scrubs credentials) rather than the bare
        # str(exc) this class used to build inline — the same fidelity
        # ToolExecutor's single-call path already had (PIR-733/PIR-794).
        assert results[0].error == "RuntimeError: tool failed"

    async def test_empty_tool_calls_returns_empty_results(self) -> None:
        """PIR-856: Aggregator needs >= 1 parent, so zero calls take a separate path."""
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=[],
                tools=[StubTool(name="other")],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["par"] == []

    async def test_rejects_non_tool_in_list(self) -> None:
        calls: list[ToolCall] = []
        with self.assertRaises(TypeError):
            with Tapestry():
                ParallelToolCaller(
                    tool_calls=calls,
                    tools=["bad"],  # type: ignore[list-item]
                    _config=KnotConfig(id="par"),
                )


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    """Guards fire before any knot is built, so these call process() directly."""

    async def test_process_rejects_non_tool_in_tools_list(self) -> None:
        with Tapestry():
            k = ParallelToolCaller.__new__(ParallelToolCaller)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a Tool"):
            await k.process(tool_calls=[], tools=["not-a-tool"])  # type: ignore[list-item]

    async def test_process_rejects_non_tool_call(self) -> None:
        tool = StubTool(name="adder")
        with Tapestry():
            k = ParallelToolCaller.__new__(ParallelToolCaller)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(TypeError, r"tool_calls\[0\] must be a ToolCall"):
            await k.process(tool_calls=["not-a-call"], tools=[tool])  # type: ignore[list-item]


class TestRunsThroughTheEngine(unittest.IsolatedAsyncioTestCase):
    """PIR-856: each call is a node now, not an inline await under asyncio.gather."""

    async def test_each_invocation_gets_its_own_lineage_row(self) -> None:
        tool = StubTool(name="adder", handler="result-value")
        call = ToolCall(tool_name="adder", arguments={}, call_id="c1")
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=[call],
                tools=[tool],
                _config=KnotConfig(id="par"),
            )

        result = await t.run(RunRequest())

        assert result.succeeded
        assert result.outputs["par"][0].result == "result-value"
        # ParallelToolCaller is a SubTapestry, so the invocation is recorded
        # in the inner run rather than beside it in the outer one.
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert "c1" in inner_knot_ids, inner_knot_ids


class TestParallelToolCallerApproval(unittest.IsolatedAsyncioTestCase):
    """PIR-865: a gated call denies as ``Skipped``, not an ``Err``."""

    async def test_approved_gated_call_runs_normally(self) -> None:
        danger = KitStubTool(
            name="danger", permissions=ToolPermissions(approval_required=True), result="ran"
        )
        calls = [ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[danger],
                approval_hook=None,
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["par"][0]
        assert view.status is ToolStatus.OK
        assert view.result == "ran"

    async def test_denied_gated_call_is_skipped_not_an_error(self) -> None:
        danger = KitStubTool(name="danger", permissions=ToolPermissions(approval_required=True))
        calls = [ToolCall(tool_name="danger", arguments={"input": "x"}, call_id="c1")]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[danger],
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["par"][0]
        assert view.status is ToolStatus.SKIPPED
        assert view.error == "call skipped: approval denied"
        assert danger.invocations == []
