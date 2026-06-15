"""Unit tests for :class:`_LoadAndChunk`."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing._load_and_chunk import (
    _LoadAndChunk,
)
from pirn.tapestry import Tapestry


def _make_knot(source: str, chunk_size: int) -> _LoadAndChunk:
    with Tapestry():
        return _LoadAndChunk(
            source=source,
            chunk_size=chunk_size,
            _config=KnotConfig(id="lac"),
        )


class TestLoadAndChunkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("abcdefghij", encoding="utf-8")
            k = _make_knot(source=fpath, chunk_size=5)
            result = await k.process(source=fpath, chunk_size=5)
            assert result == ["abcde", "fghij"]

    async def test_empty_file_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.txt")
            Path(fpath).write_text("", encoding="utf-8")
            k = _make_knot(source=fpath, chunk_size=100)
            result = await k.process(source=fpath, chunk_size=100)
            assert result == []

    async def test_rejects_empty_source(self) -> None:
        k = _make_knot(source="placeholder", chunk_size=10)
        with self.assertRaises(TypeError):
            await k.process(source="", chunk_size=10)

    async def test_rejects_zero_chunk_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello", encoding="utf-8")
            k = _make_knot(source=fpath, chunk_size=5)
            with self.assertRaises(ValueError):
                await k.process(source=fpath, chunk_size=0)
