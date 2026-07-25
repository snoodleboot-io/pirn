"""Unit tests for :class:`FactClaimExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.guardrails.fact_claim_extractor import (
    FactClaimExtractor,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> FactClaimExtractor:
    with Tapestry():
        return FactClaimExtractor(
            response=AgentResponse(content="ok", finish_reason="stop"),
            llm=llm,
            _config=KnotConfig(id="fce"),
        )


class TestFactClaimExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_claims_as_list(self) -> None:
        llm = StubLLMProvider(["Water is wet\nSky is blue"])
        k = _make_knot(llm)
        response = AgentResponse(content="Water is wet. Sky is blue.", finish_reason="stop")
        claims = await k.process(response=response, llm=llm)
        assert isinstance(claims, list)
        assert len(claims) == 2

    async def test_strips_bullet_markers(self) -> None:
        llm = StubLLMProvider(["- claim one\n* claim two\n• claim three"])
        k = _make_knot(llm)
        response = AgentResponse(content="stuff", finish_reason="stop")
        claims = await k.process(response=response, llm=llm)
        assert all(not c.startswith(("-", "*", "•")) for c in claims)

    async def test_empty_response_returns_empty_list(self) -> None:
        llm = StubLLMProvider([""])
        k = _make_knot(llm)
        response = AgentResponse(content="", finish_reason="stop")
        result = await k.process(response=response, llm=llm)
        assert result == []

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(response="not a response", llm=llm)  # type: ignore[arg-type]
