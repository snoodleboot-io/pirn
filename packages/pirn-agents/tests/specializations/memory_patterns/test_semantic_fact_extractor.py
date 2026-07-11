"""Unit tests for :class:`SemanticFactExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.memory_patterns.semantic_fact_extractor import (
    SemanticFactExtractor,
)
from pirn_agents.types.agent_message import AgentMessage
from tests.specializations.conftest import StubLLMProvider


def _make_knot() -> SemanticFactExtractor:
    with Tapestry():
        return SemanticFactExtractor(
            messages=[],
            llm=StubLLMProvider([]),
            fact_extraction_prompt="Extract facts:",
            _config=KnotConfig(id="sfe"),
        )


class TestSemanticFactExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_list_of_facts(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["Water boils at 100C\nIce melts at 0C"])
        msgs = [AgentMessage(role="user", content="tell me about water")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract facts:")
        assert isinstance(facts, list)
        assert len(facts) == 2

    async def test_strips_bullet_markers(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["- fact one\n* fact two"])
        msgs = [AgentMessage(role="user", content="hi")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract:")
        assert all(not f.startswith(("-", "*")) for f in facts)

    async def test_empty_llm_reply_returns_empty_list(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider([""])
        msgs = [AgentMessage(role="user", content="hi")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract:")
        assert facts == []

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(messages=[], llm="bad", fact_extraction_prompt="Extract:")  # type: ignore[arg-type]

    async def test_rejects_empty_fact_extraction_prompt(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider([])
        with self.assertRaises(ValueError):
            await k.process(messages=[], llm=llm, fact_extraction_prompt="")
