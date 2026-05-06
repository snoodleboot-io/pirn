"""Tests for :class:`OutputGuardrailGate`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.output_guardrail_gate import (
    OutputGuardrailGate,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry


def _make_knot() -> OutputGuardrailGate:
    with Tapestry():
        return OutputGuardrailGate(
            response=AgentResponse(content="ok", finish_reason="stop"),
            deny_patterns=(),
            allowed_tool_names=(),
            _config=KnotConfig(id="gate"),
        )


class TestOutputGuardrailGateProcessDirect(unittest.IsolatedAsyncioTestCase):
    async def test_process_passes_clean_response(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="all good", finish_reason="stop")
        result = await k.process(
            response=response,
            deny_patterns=(),
            allowed_tool_names=(),
        )
        assert isinstance(result, AgentResponse)
        assert result.content == "all good"

    async def test_process_raises_for_deny_pattern_match(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="this is BAD content", finish_reason="stop")
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                response=response,
                deny_patterns=(r"BAD",),
                allowed_tool_names=(),
            )

    async def test_process_raises_for_disallowed_tool(self) -> None:
        k = _make_knot()
        response = AgentResponse(
            content="ok",
            tool_calls=(ToolCall(tool_name="rogue", arguments={}, call_id="c1"),),
            finish_reason="stop",
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                response=response,
                deny_patterns=(),
                allowed_tool_names=("search",),
            )


class TestOutputGuardrailGateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_response_when_clean(self) -> None:
        response = AgentResponse(
            content="all good",
            tool_calls=(
                ToolCall(
                    tool_name="search",
                    arguments={"q": "x"},
                    call_id="c1",
                ),
            ),
            finish_reason="stop",
        )
        with Tapestry() as t:
            OutputGuardrailGate(
                response=response,
                deny_patterns=(r"BAD",),
                allowed_tool_names=("search",),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        validated = result.outputs["gate"]
        assert isinstance(validated, AgentResponse)
        assert validated.content == "all good"

    async def test_fails_run_when_disallowed_tool_used(self) -> None:
        response = AgentResponse(
            content="ok",
            tool_calls=(
                ToolCall(
                    tool_name="rogue",
                    arguments={},
                    call_id="c1",
                ),
            ),
            finish_reason="stop",
        )
        with Tapestry() as t:
            OutputGuardrailGate(
                response=response,
                deny_patterns=(),
                allowed_tool_names=("search",),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
