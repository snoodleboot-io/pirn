"""Tests for :class:`ReWooSynthesizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rewoo.rewoo_result import ReWooResult
from pirn_agents.specializations.rewoo.rewoo_synthesizer import ReWooSynthesizer
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus
from tests.specializations.conftest import StubLLMProvider


def _plan() -> tuple[ToolCall, ...]:
    return (
        ToolCall(tool_name="search", arguments={"input": "q"}, call_id="c0"),
        ToolCall(tool_name="calc", arguments={"input": "2+2"}, call_id="c1"),
    )


def _results() -> tuple[ToolResult, ...]:
    return (
        ToolResult(call_id="c0", result="hit", status=ToolStatus.OK),
        ToolResult(call_id="c1", result=4, status=ToolStatus.OK),
    )


class TestReWooSynthesizerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_typed_result_with_answer_plan_and_results(self) -> None:
        llm = StubLLMProvider(["the final answer"])
        with Tapestry() as t:
            ReWooSynthesizer(
                goal="solve",
                plan=_plan(),
                results=_results(),
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        out = run.outputs["synth"]
        assert isinstance(out, ReWooResult)
        assert out.answer == "the final answer"
        assert len(out.plan) == 2
        assert len(out.results) == 2

    async def test_evidence_contains_tool_results(self) -> None:
        llm = StubLLMProvider(["done"])
        with Tapestry() as t:
            ReWooSynthesizer(
                goal="solve",
                plan=_plan(),
                results=_results(),
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        await t.run(RunRequest())
        user_content = llm.calls[0][-1]["content"]
        assert "search" in user_content
        assert "'hit'" in user_content

    async def test_single_llm_round_trip(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry() as t:
            ReWooSynthesizer(
                goal="g",
                plan=_plan(),
                results=_results(),
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 1

    async def test_rejects_non_tool_call_plan(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            knot = ReWooSynthesizer.__new__(ReWooSynthesizer)
            object.__setattr__(knot, "_config", KnotConfig(id="synth"))
        with self.assertRaises(TypeError):
            await knot.process(goal="g", plan=("bad",), results=(), llm=llm)  # type: ignore[arg-type]
