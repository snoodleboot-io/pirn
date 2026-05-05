"""Unit tests for :class:`CitationGrounder`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.guardrails.citation_grounder import (
    CitationGrounder,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestCitationGrounderConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                CitationGrounder(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    sources=["src"],
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cg"),
                )


class TestCitationGrounderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rewrites_content_with_citation(self) -> None:
        llm = StubLLMProvider(["The sky is blue [1]."])
        response = AgentResponse(content="The sky is blue.", finish_reason="stop")
        with Tapestry() as t:
            CitationGrounder(
                response=response,
                sources=["The sky is blue because of Rayleigh scattering."],
                llm=llm,
                _config=KnotConfig(id="cg"),
            )
        result = await t.run(RunRequest())
        grounded = result.outputs["cg"]
        assert isinstance(grounded, AgentResponse)
        assert "[1]" in grounded.content

    async def test_preserves_finish_reason(self) -> None:
        llm = StubLLMProvider(["cited content"])
        response = AgentResponse(content="raw", finish_reason="length")
        with Tapestry() as t:
            CitationGrounder(
                response=response,
                sources=["src"],
                llm=llm,
                _config=KnotConfig(id="cg"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["cg"].finish_reason == "length"

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaises(TypeError):
                CitationGrounder(
                    response="not a response",  # type: ignore[arg-type]
                    sources=["src"],
                    llm=llm,
                    _config=KnotConfig(id="cg"),
                )
