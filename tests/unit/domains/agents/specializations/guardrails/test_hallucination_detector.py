"""Unit tests for :class:`HallucinationDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.guardrails.hallucination_detector import (
    HallucinationDetector,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> HallucinationDetector:
    with Tapestry():
        return HallucinationDetector(
            response=AgentResponse(content="ok", finish_reason="stop"),
            sources=[],
            llm=llm,
            _config=KnotConfig(id="hd"),
        )


class TestHallucinationDetectorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_no_hallucinations_when_llm_returns_none(self) -> None:
        llm = StubLLMProvider(["NONE"])
        k = _make_knot(llm)
        response = AgentResponse(content="Supported claim.", finish_reason="stop")
        detection = await k.process(
            response=response,
            sources=["Supported claim is true."],
            llm=llm,
        )
        assert detection["has_hallucinations"] is False
        assert detection["flagged_claims"] == []

    async def test_flags_hallucinated_claims(self) -> None:
        llm = StubLLMProvider(["The moon is made of cheese"])
        k = _make_knot(llm)
        response = AgentResponse(content="The moon is made of cheese.", finish_reason="stop")
        detection = await k.process(
            response=response,
            sources=["The moon is a rocky satellite."],
            llm=llm,
        )
        assert detection["has_hallucinations"] is True
        assert len(detection["flagged_claims"]) == 1

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["NONE"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", sources=[], llm=llm)  # type: ignore[arg-type]
