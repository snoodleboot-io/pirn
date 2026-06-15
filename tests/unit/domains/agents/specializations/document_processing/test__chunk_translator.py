"""Unit tests for :class:`_ChunkTranslator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing._chunk_translator import (
    _ChunkTranslator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> _ChunkTranslator:
    with Tapestry():
        return _ChunkTranslator(
            chunks=[],
            target_language="French",
            llm=llm,
            _config=KnotConfig(id="ct"),
        )


class TestChunkTranslatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_empty_string(self) -> None:
        llm = StubLLMProvider([])
        k = _make_knot(llm)
        result = await k.process(chunks=[], target_language="French", llm=llm)
        assert result == ""

    async def test_single_chunk_translated(self) -> None:
        llm = StubLLMProvider(["Bonjour"])
        k = _make_knot(llm)
        result = await k.process(chunks=["Hello"], target_language="French", llm=llm)
        assert result == "Bonjour"

    async def test_multiple_chunks_concatenated(self) -> None:
        llm = StubLLMProvider(["Un", "Deux"])
        k = _make_knot(llm)
        result = await k.process(chunks=["One", "Two"], target_language="French", llm=llm)
        assert result == "UnDeux"

    async def test_llm_called_once_per_chunk(self) -> None:
        llm = StubLLMProvider(["x", "y", "z"])
        k = _make_knot(llm)
        await k.process(chunks=["a", "b", "c"], target_language="Spanish", llm=llm)
        assert len(llm.calls) == 3

    async def test_target_language_in_system_prompt(self) -> None:
        llm = StubLLMProvider(["hola"])
        k = _make_knot(llm)
        await k.process(chunks=["hello"], target_language="Spanish", llm=llm)
        system_content = llm.calls[0][0]["content"]
        assert "Spanish" in system_content
