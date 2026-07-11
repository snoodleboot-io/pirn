"""Unit tests for :class:`_QALoadAndChunk`."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._qa_load_and_chunk import (
    _QALoadAndChunk,
)


def _make_knot(source: str, chunk_size: int) -> _QALoadAndChunk:
    with Tapestry():
        return _QALoadAndChunk(
            source=source,
            chunk_size=chunk_size,
            _config=KnotConfig(id="qa_lac"),
        )


class TestQALoadAndChunkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello world!", encoding="utf-8")
            k = _make_knot(source=fpath, chunk_size=6)
            chunks = await k.process(source=fpath, chunk_size=6)
            assert isinstance(chunks, list)
            assert "".join(chunks) == "hello world!"

    async def test_empty_file_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.txt")
            Path(fpath).write_text("", encoding="utf-8")
            k = _make_knot(source=fpath, chunk_size=100)
            result = await k.process(source=fpath, chunk_size=100)
            assert result == []
