"""Unit tests for :class:`_ChunkSummariser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._chunk_summariser import (
    _ChunkSummariser,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> _ChunkSummariser:
    with Tapestry():
        return _ChunkSummariser(
            chunk="",
            position="",
            llm=llm,
            _config=KnotConfig(id="chunk_summaries"),
        )


class TestChunkSummariserProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_summary(self) -> None:
        llm = StubLLMProvider(["short summary"])
        result = await _make_knot(llm).process(
            chunk="long text here", position="Chunk 1 of 1", llm=llm
        )
        assert result == "short summary"
        assert len(llm.calls) == 1

    async def test_user_message_embeds_the_position(self) -> None:
        """Pins the ``"Chunk i of n."`` text nothing else in the repo asserts.

        Without this pin, "simplify away the index" would ship silently — and
        the index is the whole reason the fan-out needs ZipMap over Map.
        """
        llm = StubLLMProvider(["s"])
        await _make_knot(llm).process(chunk="body", position="Chunk 1 of 2", llm=llm)
        assert llm.calls[0][1]["content"] == "Chunk 1 of 2.\n\nbody"

    async def test_extracts_text_from_a_content_mapping(self) -> None:
        assert _ChunkSummariser._extract_text({"content": "hello"}) == "hello"
        assert _ChunkSummariser._extract_text({"content": [{"text": "hi"}]}) == "hi"
        assert _ChunkSummariser._extract_text("plain") == "plain"
