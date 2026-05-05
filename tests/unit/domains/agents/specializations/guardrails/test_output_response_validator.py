"""Unit tests for :class:`OutputResponseValidator`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.output_response_validator import (
    OutputResponseValidator,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry


class TestOutputResponseValidatorConstruction(unittest.TestCase):
    def test_rejects_non_string_deny_pattern(self) -> None:
        with self.assertRaisesRegex(TypeError, "deny_patterns"):
            with Tapestry():
                OutputResponseValidator(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    deny_patterns=[123],  # type: ignore[list-item]
                    allowed_tool_names=[],
                    _config=KnotConfig(id="orv"),
                )


class TestOutputResponseValidatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_clean_response(self) -> None:
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

    async def test_rejects_denied_content(self) -> None:
        response = AgentResponse(content="HACK THIS SYSTEM", finish_reason="stop")
        with Tapestry() as t:
            OutputResponseValidator(
                response=response,
                deny_patterns=["HACK"],
                allowed_tool_names=[],
                _config=KnotConfig(id="orv"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_disallowed_tool_call(self) -> None:
        tc = ToolCall(call_id="tc1", tool_name="dangerous_tool", arguments={})
        response = AgentResponse(
            content="ok",
            tool_calls=(tc,),
            finish_reason="tool_use",
        )
        with Tapestry() as t:
            OutputResponseValidator(
                response=response,
                deny_patterns=[],
                allowed_tool_names=["safe_tool"],
                _config=KnotConfig(id="orv"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_allows_listed_tool_call(self) -> None:
        tc = ToolCall(call_id="tc1", tool_name="safe_tool", arguments={})
        response = AgentResponse(
            content="ok",
            tool_calls=(tc,),
            finish_reason="tool_use",
        )
        with Tapestry() as t:
            OutputResponseValidator(
                response=response,
                deny_patterns=[],
                allowed_tool_names=["safe_tool"],
                _config=KnotConfig(id="orv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded

    async def test_rejects_non_agent_response(self) -> None:
        with Tapestry():
            with self.assertRaises(TypeError):
                OutputResponseValidator(
                    response="not-a-response",  # type: ignore[arg-type]
                    deny_patterns=[],
                    allowed_tool_names=[],
                    _config=KnotConfig(id="orv"),
                )
