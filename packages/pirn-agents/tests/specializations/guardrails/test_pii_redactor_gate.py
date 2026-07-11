"""Tests for :class:`PiiRedactorCheck` (formerly ``PIIRedactorGate``)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.guardrails.pii_redactor_check import (
    PiiRedactorCheck,
)
from pirn_agents.types.agent_response import AgentResponse


def _make_knot() -> PiiRedactorCheck:
    with Tapestry():
        return PiiRedactorCheck(
            response=AgentResponse(content="ok", finish_reason="stop"),
            _config=KnotConfig(id="pii"),
        )


class TestPiiRedactorCheckProcess(unittest.IsolatedAsyncioTestCase):
    async def test_default_patterns_redact_email_and_ssn(self) -> None:
        response = AgentResponse(
            content="contact me@x.com or 555-12-3456 today",
            finish_reason="stop",
        )
        with Tapestry() as t:
            PiiRedactorCheck(response=response, _config=KnotConfig(id="pii"))
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["pii"]
        assert isinstance(result, AgentResponse)
        assert "me@x.com" not in result.content
        assert "555-12-3456" not in result.content
        assert result.content.count("<redacted>") == 2

    async def test_returns_response_unchanged_when_no_match(self) -> None:
        response = AgentResponse(content="completely benign content", finish_reason="stop")
        with Tapestry() as t:
            PiiRedactorCheck(
                response=response,
                patterns=(r"\bSSN-\d+\b",),
                _config=KnotConfig(id="pii"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["pii"]
        assert isinstance(result, AgentResponse)
        assert result.content == "completely benign content"

    async def test_custom_pattern_redacts_match(self) -> None:
        response = AgentResponse(content="my id is ID-99999", finish_reason="stop")
        with Tapestry() as t:
            PiiRedactorCheck(
                response=response,
                patterns=(r"ID-\d+",),
                _config=KnotConfig(id="pii"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["pii"]
        assert "<redacted>" in result.content
        assert "ID-99999" not in result.content

    async def test_tapestry_run_integration(self) -> None:
        response = AgentResponse(
            content="contact me@x.com today",
            finish_reason="stop",
        )
        with Tapestry() as t:
            PiiRedactorCheck(
                response=response,
                _config=KnotConfig(id="pii"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        redacted = result.outputs["pii"]
        assert isinstance(redacted, AgentResponse)
        assert "me@x.com" not in redacted.content
