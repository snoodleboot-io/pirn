"""Unit tests for :class:`_DocumentChunker`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._document_chunker import (
    _DocumentChunker,
)
from pirn.tapestry import Tapestry


class TestDocumentChunkerConstruction(unittest.TestCase):
    pass  # no construction guards; validation is in process()


class TestDocumentChunkerProcess(unittest.IsolatedAsyncioTestCase):
    async def _run(self, text, chunk_size=10, chunk_overlap=0):
        with Tapestry() as t:
            _DocumentChunker(
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                _config=KnotConfig(id="dc"),
            )
        result = await t.run(RunRequest())
        return result.outputs["dc"]

    async def test_empty_text_returns_empty_list(self) -> None:
        chunks = await self._run("")
        assert chunks == []

    async def test_single_chunk_when_text_fits(self) -> None:
        chunks = await self._run("hello", chunk_size=10)
        assert chunks == ["hello"]

    async def test_splits_into_multiple_chunks(self) -> None:
        text = "a" * 20
        chunks = await self._run(text, chunk_size=10, chunk_overlap=0)
        assert len(chunks) == 2

    async def test_overlap_shared_between_adjacent_chunks(self) -> None:
        text = "0123456789"  # 10 chars
        chunks = await self._run(text, chunk_size=6, chunk_overlap=2)
        # stride = 4; chunk0=0-5, chunk1=4-9
        assert chunks[0] == "012345"
        assert chunks[1] == "456789"

    async def test_invalid_chunk_size_raises(self) -> None:
        with Tapestry() as t:
            _DocumentChunker(
                text="hello",
                chunk_size=0,
                chunk_overlap=0,
                _config=KnotConfig(id="dc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_invalid_chunk_overlap_raises(self) -> None:
        with Tapestry() as t:
            _DocumentChunker(
                text="hello",
                chunk_size=5,
                chunk_overlap=5,  # must be < chunk_size
                _config=KnotConfig(id="dc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
