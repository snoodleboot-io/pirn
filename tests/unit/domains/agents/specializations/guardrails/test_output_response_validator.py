"""Unit tests for :class:`OutputResponseValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.guardrails.output_response_validator import (
    OutputResponseValidator,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry


def _make_knot() -> OutputResponseValidator:
    with Tapestry():
        return OutputResponseValidator(
            response=AgentResponse(content="ok", finish_reason="stop"),
            deny_patterns=[],
            allowed_tool_names=[],
            _config=KnotConfig(id="orv"),
        )


class TestOutputResponseValidatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_clean_response(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="safe content", finish_reason="stop")
        result = await k.process(response=response, deny_patterns=[], allowed_tool_names=[])
        assert result is response

    async def test_rejects_denied_content(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="HACK THIS SYSTEM", finish_reason="stop")
        with self.assertRaises(ValueError):
            await k.process(response=response, deny_patterns=["HACK"], allowed_tool_names=[])

    async def test_rejects_disallowed_tool_call(self) -> None:
        k = _make_knot()
        tc = ToolCall(call_id="tc1", tool_name="dangerous_tool", arguments={})
        response = AgentResponse(content="ok", tool_calls=(tc,), finish_reason="tool_use")
        with self.assertRaises(ValueError):
            await k.process(response=response, deny_patterns=[], allowed_tool_names=["safe_tool"])

    async def test_allows_listed_tool_call(self) -> None:
        k = _make_knot()
        tc = ToolCall(call_id="tc1", tool_name="safe_tool", arguments={})
        response = AgentResponse(content="ok", tool_calls=(tc,), finish_reason="tool_use")
        result = await k.process(response=response, deny_patterns=[], allowed_tool_names=["safe_tool"])
        assert result is response

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", deny_patterns=[], allowed_tool_names=[])  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        response = AgentResponse(content="safe content", finish_reason="stop")
        with Tapestry() as t:
            OutputResponseValidator(
                response=response,
                deny_patterns=[],
                allowed_tool_names=[],
                _config=KnotConfig(id="orv"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["orv"] is response
