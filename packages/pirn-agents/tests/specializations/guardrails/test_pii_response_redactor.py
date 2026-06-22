"""Unit tests for :class:`PIIResponseRedactor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.guardrails.pii_response_redactor import (
    PIIResponseRedactor,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> PIIResponseRedactor:
    with Tapestry():
        return PIIResponseRedactor(
            response=AgentResponse(content="ok", finish_reason="stop"),
            patterns=[],
            _config=KnotConfig(id="prr"),
        )


class TestPIIResponseRedactorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_redacts_matching_pii(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="Call me at 555-1234.", finish_reason="stop")
        out = await k.process(response=response, patterns=[r"\d{3}-\d{4}"])
        assert "<redacted>" in out.content
        assert "555-1234" not in out.content

    async def test_returns_original_when_no_match(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="no pii here", finish_reason="stop")
        out = await k.process(response=response, patterns=[r"\d{3}-\d{4}"])
        assert out is response

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", patterns=[])  # type: ignore[arg-type]

    async def test_preserves_finish_reason_and_usage(self) -> None:
        k = _make_knot()
        response = AgentResponse(
            content="my ssn is 123-45-6789",
            finish_reason="stop",
            usage={"input_tokens": 5},
        )
        out = await k.process(response=response, patterns=[r"\d{3}-\d{2}-\d{4}"])
        assert out.finish_reason == "stop"
        assert out.usage["input_tokens"] == 5

    async def test_tapestry_run_integration(self) -> None:
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
