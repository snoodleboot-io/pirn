"""Unit tests for :class:`_DocumentChunker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing._document_chunker import (
    _DocumentChunker,
)
from pirn.tapestry import Tapestry


def _make_knot() -> _DocumentChunker:
    with Tapestry():
        return _DocumentChunker(
            text="",
            chunk_size=10,
            chunk_overlap=0,
            _config=KnotConfig(id="dc"),
        )


class TestDocumentChunkerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_text_returns_empty_list(self) -> None:
        k = _make_knot()
        result = await k.process(text="", chunk_size=10, chunk_overlap=0)
        assert result == []

    async def test_single_chunk_when_text_fits(self) -> None:
        k = _make_knot()
        result = await k.process(text="hello", chunk_size=10, chunk_overlap=0)
        assert result == ["hello"]

    async def test_splits_into_multiple_chunks(self) -> None:
        k = _make_knot()
        result = await k.process(text="a" * 20, chunk_size=10, chunk_overlap=0)
        assert len(result) == 2

    async def test_overlap_shared_between_adjacent_chunks(self) -> None:
        k = _make_knot()
        result = await k.process(text="0123456789", chunk_size=6, chunk_overlap=2)
        # stride = 4; chunk0=0-5, chunk1=4-9
        assert result[0] == "012345"
        assert result[1] == "456789"

    async def test_invalid_chunk_size_raises(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await k.process(text="hello", chunk_size=0, chunk_overlap=0)

    async def test_invalid_chunk_overlap_raises(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await k.process(text="hello", chunk_size=5, chunk_overlap=5)
