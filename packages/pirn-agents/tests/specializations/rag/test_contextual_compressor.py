"""Tests for :class:`ContextualCompressor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.contextual_compressor import ContextualCompressor
from tests.specializations.conftest import StubLLMProvider


def _compressor() -> ContextualCompressor:
    with Tapestry():
        knot = ContextualCompressor.__new__(ContextualCompressor)
        object.__setattr__(knot, "_config", KnotConfig(id="compress"))
    return knot


class TestContextualCompressor(unittest.IsolatedAsyncioTestCase):
    async def test_compresses_and_drops_irrelevant(self) -> None:
        # First doc -> relevant span; second doc -> NONE (dropped).
        llm = StubLLMProvider(["relevant span", "NONE"])
        knot = _compressor()
        docs = await knot.process(
            query="q",
            documents=[{"id": "1", "text": "long relevant text"}, {"id": "2", "text": "noise"}],
            llm=llm,
        )
        assert len(docs) == 1
        assert docs[0]["id"] == "1"
        assert docs[0]["text"] == "relevant span"
        assert docs[0]["compressed"] is True

    async def test_preserves_identity_keys(self) -> None:
        llm = StubLLMProvider(["kept"])
        knot = _compressor()
        docs = await knot.process(
            query="q", documents=[{"id": "x", "score": 0.9, "text": "t"}], llm=llm
        )
        assert docs[0]["id"] == "x"
        assert docs[0]["score"] == 0.9

    async def test_rejects_non_llm(self) -> None:
        knot = _compressor()
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(query="q", documents=[], llm="nope")  # type: ignore[arg-type]
