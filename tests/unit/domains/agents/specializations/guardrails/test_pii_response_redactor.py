"""Unit tests for :class:`PIIResponseRedactor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.pii_response_redactor import (
    PIIResponseRedactor,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class TestPIIResponseRedactorConstruction(unittest.TestCase):
    def test_rejects_non_string_pattern(self) -> None:
        with self.assertRaisesRegex(TypeError, "patterns"):
            with Tapestry():
                PIIResponseRedactor(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    patterns=[123],  # type: ignore[list-item]
                    _config=KnotConfig(id="prr"),
                )


class TestPIIResponseRedactorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_redacts_matching_pii(self) -> None:
        response = AgentResponse(content="Call me at 555-1234.", finish_reason="stop")
        with Tapestry() as t:
            PIIResponseRedactor(
                response=response,
                patterns=[r"\d{3}-\d{4}"],
                _config=KnotConfig(id="prr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["prr"]
        assert "<redacted>" in out.content
        assert "555-1234" not in out.content

    async def test_returns_original_when_no_match(self) -> None:
        response = AgentResponse(content="no pii here", finish_reason="stop")
        with Tapestry() as t:
            PIIResponseRedactor(
                response=response,
                patterns=[r"\d{3}-\d{4}"],
                _config=KnotConfig(id="prr"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["prr"] is response

    async def test_rejects_non_agent_response(self) -> None:
        with Tapestry():
            with self.assertRaises(TypeError):
                PIIResponseRedactor(
                    response="not-a-response",  # type: ignore[arg-type]
                    patterns=[],
                    _config=KnotConfig(id="prr"),
                )

    async def test_preserves_finish_reason_and_usage(self) -> None:
        response = AgentResponse(
            content="my ssn is 123-45-6789",
            finish_reason="stop",
            usage={"input_tokens": 5},
        )
        with Tapestry() as t:
            PIIResponseRedactor(
                response=response,
                patterns=[r"\d{3}-\d{2}-\d{4}"],
                _config=KnotConfig(id="prr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["prr"]
        assert out.finish_reason == "stop"
        assert out.usage["input_tokens"] == 5
