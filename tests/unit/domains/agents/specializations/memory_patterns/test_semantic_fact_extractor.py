"""Unit tests for :class:`SemanticFactExtractor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.memory_patterns.semantic_fact_extractor import (
    SemanticFactExtractor,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestSemanticFactExtractorConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                SemanticFactExtractor(
                    messages=[],
                    llm="bad",  # type: ignore[arg-type]
                    fact_extraction_prompt="Extract facts:",
                    _config=KnotConfig(id="sfe"),
                )

    def test_rejects_empty_fact_extraction_prompt(self) -> None:
        from tests.unit.domains.agents.specializations.conftest import StubLLMProvider
        with self.assertRaisesRegex(ValueError, "fact_extraction_prompt"):
            with Tapestry():
                SemanticFactExtractor(
                    messages=[],
                    llm=StubLLMProvider([]),
                    fact_extraction_prompt="",
                    _config=KnotConfig(id="sfe"),
                )


class TestSemanticFactExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_list_of_facts(self) -> None:
        llm = StubLLMProvider(["Water boils at 100C\nIce melts at 0C"])
        msgs = [AgentMessage(role="user", content="tell me about water")]
        with Tapestry() as t:
            SemanticFactExtractor(
                messages=msgs,
                llm=llm,
                fact_extraction_prompt="Extract facts from the conversation:",
                _config=KnotConfig(id="sfe"),
            )
        result = await t.run(RunRequest())
        facts = result.outputs["sfe"]
        assert isinstance(facts, list)
        assert len(facts) == 2

    async def test_strips_bullet_markers(self) -> None:
        llm = StubLLMProvider(["- fact one\n* fact two"])
        msgs = [AgentMessage(role="user", content="hi")]
        with Tapestry() as t:
            SemanticFactExtractor(
                messages=msgs,
                llm=llm,
                fact_extraction_prompt="Extract:",
                _config=KnotConfig(id="sfe"),
            )
        result = await t.run(RunRequest())
        facts = result.outputs["sfe"]
        assert all(not f.startswith(("-", "*")) for f in facts)

    async def test_empty_llm_reply_returns_empty_list(self) -> None:
        llm = StubLLMProvider([""])
        msgs = [AgentMessage(role="user", content="hi")]
        with Tapestry() as t:
            SemanticFactExtractor(
                messages=msgs,
                llm=llm,
                fact_extraction_prompt="Extract:",
                _config=KnotConfig(id="sfe"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sfe"] == []
