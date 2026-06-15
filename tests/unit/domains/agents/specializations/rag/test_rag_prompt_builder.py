"""Unit tests for :class:`RAGPromptBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.rag.rag_prompt_builder import RAGPromptBuilder
from pirn.tapestry import Tapestry


class _RetrievedSource(Knot):
    def __init__(self, hits, *, _config, **kwargs):
        self._hits = hits
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._hits


class TestRAGPromptBuilderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_instruction(self) -> None:
        knot = RAGPromptBuilder(
            query="q",
            retrieved=_RetrievedSource([], _config=KnotConfig(id="src")),
            _config=KnotConfig(id="rpb"),
        )
        with self.assertRaisesRegex(ValueError, "instruction"):
            await knot.process(query="q", retrieved=[], instruction="")

    async def test_rejects_non_string_query(self) -> None:
        knot = RAGPromptBuilder(
            query="q",
            retrieved=_RetrievedSource([], _config=KnotConfig(id="src")),
            _config=KnotConfig(id="rpb"),
        )
        with self.assertRaises(TypeError):
            await knot.process(
                query=42,  # type: ignore[arg-type]
                retrieved=[],
                instruction="Answer the question using the retrieved context.",
            )

    async def test_builds_prompt_with_context(self) -> None:
        hits = [{"text": "relevant doc"}]
        with Tapestry() as t:
            src = _RetrievedSource(hits, _config=KnotConfig(id="src"))
            RAGPromptBuilder(
                query="What is X?",
                retrieved=src,
                _config=KnotConfig(id="rpb"),
            )
        result = await t.run(RunRequest())
        prompt = result.outputs["rpb"]
        assert "What is X?" in prompt
        assert "relevant doc" in prompt

    async def test_empty_retrieved_shows_no_context_message(self) -> None:
        with Tapestry() as t:
            src = _RetrievedSource([], _config=KnotConfig(id="src"))
            RAGPromptBuilder(
                query="question",
                retrieved=src,
                _config=KnotConfig(id="rpb"),
            )
        result = await t.run(RunRequest())
        prompt = result.outputs["rpb"]
        assert "no context retrieved" in prompt
