"""Unit tests for :class:`HallucinationDetector`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.hallucination_detector import (
    HallucinationDetector,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestHallucinationDetectorConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                HallucinationDetector(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    sources=["src"],
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="hd"),
                )


class TestHallucinationDetectorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_no_hallucinations_when_llm_returns_none(self) -> None:
        llm = StubLLMProvider(["NONE"])
        response = AgentResponse(content="Supported claim.", finish_reason="stop")
        with Tapestry() as t:
            HallucinationDetector(
                response=response,
                sources=["Supported claim is true."],
                llm=llm,
                _config=KnotConfig(id="hd"),
            )
        result = await t.run(RunRequest())
        detection = result.outputs["hd"]
        assert detection["has_hallucinations"] is False
        assert detection["flagged_claims"] == []

    async def test_flags_hallucinated_claims(self) -> None:
        llm = StubLLMProvider(["The moon is made of cheese"])
        response = AgentResponse(content="The moon is made of cheese.", finish_reason="stop")
        with Tapestry() as t:
            HallucinationDetector(
                response=response,
                sources=["The moon is a rocky satellite."],
                llm=llm,
                _config=KnotConfig(id="hd"),
            )
        result = await t.run(RunRequest())
        detection = result.outputs["hd"]
        assert detection["has_hallucinations"] is True
        assert len(detection["flagged_claims"]) == 1

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["NONE"])
        with Tapestry():
            with self.assertRaises(TypeError):
                HallucinationDetector(
                    response="not-a-response",  # type: ignore[arg-type]
                    sources=[],
                    llm=llm,
                    _config=KnotConfig(id="hd"),
                )
