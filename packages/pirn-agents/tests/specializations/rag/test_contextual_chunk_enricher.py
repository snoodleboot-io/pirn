"""Tests for :class:`ContextualChunkEnricher`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.contextual_chunk_enricher import ContextualChunkEnricher
from tests.specializations.conftest import StubLLMProvider


def _enricher() -> ContextualChunkEnricher:
    with Tapestry():
        knot = ContextualChunkEnricher.__new__(ContextualChunkEnricher)
        object.__setattr__(knot, "_config", KnotConfig(id="enrich"))
    return knot


class TestContextualChunkEnricher(unittest.IsolatedAsyncioTestCase):
    async def test_prepends_context(self) -> None:
        llm = StubLLMProvider(["From the intro section."])
        knot = _enricher()
        docs = await knot.process(
            documents=[{"text": "the model has 7B params"}],
            document_text="A full paper about a 7B model.",
            llm=llm,
        )
        assert docs[0]["context"] == "From the intro section."
        assert docs[0]["raw_text"] == "the model has 7B params"
        assert docs[0]["text"].startswith("From the intro section.")
        assert "7B params" in docs[0]["text"]

    async def test_rejects_non_string_document_text(self) -> None:
        knot = _enricher()
        with self.assertRaisesRegex(TypeError, "document_text must be a string"):
            await knot.process(documents=[], document_text=1, llm=StubLLMProvider(["x"]))  # type: ignore[arg-type]
