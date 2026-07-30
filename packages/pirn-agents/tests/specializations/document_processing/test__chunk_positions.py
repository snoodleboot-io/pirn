"""Unit tests for :class:`_ChunkPositions`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._chunk_positions import (
    _ChunkPositions,
)


def _make_knot() -> _ChunkPositions:
    with Tapestry():
        return _ChunkPositions(chunks=[], _config=KnotConfig(id="positions"))


class TestChunkPositionsProcess(unittest.IsolatedAsyncioTestCase):
    async def test_labels_are_one_based_and_carry_the_total(self) -> None:
        result = await _make_knot().process(chunks=["a", "b", "c"])
        assert result == ["Chunk 1 of 3", "Chunk 2 of 3", "Chunk 3 of 3"]

    async def test_single_chunk(self) -> None:
        assert await _make_knot().process(chunks=["only"]) == ["Chunk 1 of 1"]

    async def test_no_chunks_yields_no_labels(self) -> None:
        """An empty list gives the ZipMap zero invocations."""
        assert await _make_knot().process(chunks=[]) == []
