"""Tests for :class:`InputGuardrailGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.input_guardrail_gate import (
    InputGuardrailGate,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestInputGuardrailGateConstruction:
    async def test_rejects_non_string_deny_pattern(self) -> None:
        with pytest.raises(TypeError, match="deny_patterns"):
            with Tapestry():
                InputGuardrailGate(
                    messages=(AgentMessage(role="user", content="hi"),),
                    deny_patterns=(123,),  # type: ignore[arg-type]
                    _config=KnotConfig(id="gate"),
                )

    async def test_rejects_non_string_pii_pattern(self) -> None:
        with pytest.raises(TypeError, match="pii_patterns"):
            with Tapestry():
                InputGuardrailGate(
                    messages=(AgentMessage(role="user", content="hi"),),
                    deny_patterns=(),
                    pii_patterns=(456,),  # type: ignore[arg-type]
                    _config=KnotConfig(id="gate"),
                )


@pytest.mark.asyncio
class TestInputGuardrailGateHappyPath:
    async def test_redacts_pii_and_passes_clean_messages_through(
        self,
    ) -> None:
        messages = (
            AgentMessage(role="user", content="email me at me@x.com"),
            AgentMessage(role="user", content="hello world"),
        )
        with Tapestry() as t:
            InputGuardrailGate(
                messages=messages,
                deny_patterns=(r"DROP TABLE",),
                pii_patterns=(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                ),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        cleaned = result.outputs["gate"]
        assert isinstance(cleaned, tuple)
        assert cleaned[0].content == "email me at <redacted>"
        assert cleaned[1].content == "hello world"

    async def test_deny_pattern_match_fails_run(self) -> None:
        messages = (
            AgentMessage(role="user", content="please DROP TABLE users"),
        )
        with Tapestry() as t:
            InputGuardrailGate(
                messages=messages,
                deny_patterns=(r"DROP TABLE",),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert any(
            "deny pattern" in (record.traceback_text or "")
            for record in result.exceptions
        )
