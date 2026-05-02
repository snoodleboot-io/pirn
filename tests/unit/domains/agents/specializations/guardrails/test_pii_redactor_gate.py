"""Tests for :class:`PIIRedactorGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.pii_redactor_gate import (
    PIIRedactorGate,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestPIIRedactorGateConstruction:
    async def test_rejects_non_string_pattern(self) -> None:
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="patterns"):
            with Tapestry():
                PIIRedactorGate(
                    response=response,
                    patterns=(789,),  # type: ignore[arg-type]
                    _config=KnotConfig(id="pii"),
                )


@pytest.mark.asyncio
class TestPIIRedactorGateHappyPath:
    async def test_default_patterns_redact_email_and_ssn(self) -> None:
        response = AgentResponse(
            content="contact me@x.com or 555-12-3456 today",
            finish_reason="stop",
        )
        with Tapestry() as t:
            PIIRedactorGate(
                response=response,
                _config=KnotConfig(id="pii"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        redacted = result.outputs["pii"]
        assert isinstance(redacted, AgentResponse)
        assert "me@x.com" not in redacted.content
        assert "555-12-3456" not in redacted.content
        assert redacted.content.count("<redacted>") == 2

    async def test_returns_response_unchanged_when_no_match(self) -> None:
        response = AgentResponse(
            content="completely benign content",
            finish_reason="stop",
        )
        with Tapestry() as t:
            PIIRedactorGate(
                response=response,
                patterns=(r"\bSSN-\d+\b",),
                _config=KnotConfig(id="pii"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        redacted = result.outputs["pii"]
        assert isinstance(redacted, AgentResponse)
        assert redacted.content == "completely benign content"
