"""Unit tests for :class:`FactClaimExtractor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.fact_claim_extractor import (
    FactClaimExtractor,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestFactClaimExtractorConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                FactClaimExtractor(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fce"),
                )


class TestFactClaimExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_claims_as_list(self) -> None:
        llm = StubLLMProvider(["Water is wet\nSky is blue"])
        response = AgentResponse(content="Water is wet. Sky is blue.", finish_reason="stop")
        with Tapestry() as t:
            FactClaimExtractor(
                response=response,
                llm=llm,
                _config=KnotConfig(id="fce"),
            )
        result = await t.run(RunRequest())
        claims = result.outputs["fce"]
        assert isinstance(claims, list)
        assert len(claims) == 2

    async def test_strips_bullet_markers(self) -> None:
        llm = StubLLMProvider(["- claim one\n* claim two\n• claim three"])
        response = AgentResponse(content="stuff", finish_reason="stop")
        with Tapestry() as t:
            FactClaimExtractor(
                response=response,
                llm=llm,
                _config=KnotConfig(id="fce"),
            )
        result = await t.run(RunRequest())
        claims = result.outputs["fce"]
        assert all(not c.startswith(("-", "*", "•")) for c in claims)

    async def test_empty_response_returns_empty_list(self) -> None:
        llm = StubLLMProvider([""])
        response = AgentResponse(content="", finish_reason="stop")
        with Tapestry() as t:
            FactClaimExtractor(
                response=response,
                llm=llm,
                _config=KnotConfig(id="fce"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["fce"] == []

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaises(TypeError):
                FactClaimExtractor(
                    response="not a response",  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="fce"),
                )
