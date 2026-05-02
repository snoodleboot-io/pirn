"""Tests for :class:`OutputGuardrailGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.output_guardrail_gate import (
    OutputGuardrailGate,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestOutputGuardrailGateConstruction:
    async def test_rejects_non_string_deny_pattern(self) -> None:
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="deny_patterns"):
            with Tapestry():
                OutputGuardrailGate(
                    response=response,
                    deny_patterns=(123,),  # type: ignore[arg-type]
                    allowed_tool_names=(),
                    _config=KnotConfig(id="gate"),
                )

    async def test_rejects_non_string_tool_name(self) -> None:
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="allowed_tool_names"):
            with Tapestry():
                OutputGuardrailGate(
                    response=response,
                    deny_patterns=(),
                    allowed_tool_names=(456,),  # type: ignore[arg-type]
                    _config=KnotConfig(id="gate"),
                )


@pytest.mark.asyncio
class TestOutputGuardrailGateHappyPath:
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
        assert any(
            record.exc_type == "SubTapestryError"
            for record in result.exceptions
        )
