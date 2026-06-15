"""Unit tests for :class:`CitationGrounder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.guardrails.citation_grounder import (
    CitationGrounder,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> CitationGrounder:
    with Tapestry():
        return CitationGrounder(
            response=AgentResponse(content="ok", finish_reason="stop"),
            sources=[],
            llm=llm,
            _config=KnotConfig(id="cg"),
        )


class TestCitationGrounderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rewrites_content_with_citation(self) -> None:
        llm = StubLLMProvider(["The sky is blue [1]."])
        k = _make_knot(llm)
        response = AgentResponse(content="The sky is blue.", finish_reason="stop")
        grounded = await k.process(
            response=response,
            sources=["The sky is blue because of Rayleigh scattering."],
            llm=llm,
        )
        assert isinstance(grounded, AgentResponse)
        assert "[1]" in grounded.content

    async def test_preserves_finish_reason(self) -> None:
        llm = StubLLMProvider(["cited content"])
        k = _make_knot(llm)
        response = AgentResponse(content="raw", finish_reason="length")
        result = await k.process(response=response, sources=["src"], llm=llm)
        assert result.finish_reason == "length"

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(response="not a response", sources=["src"], llm=llm)  # type: ignore[arg-type]
