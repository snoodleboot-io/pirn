"""Unit tests for :class:`_LoadAndChunk`."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._load_and_chunk import (
    _LoadAndChunk,
)
from pirn.tapestry import Tapestry


class TestLoadAndChunkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("abcdefghij", encoding="utf-8")
            with Tapestry() as t:
                _LoadAndChunk(
                    source=fpath,
                    chunk_size=5,
                    _config=KnotConfig(id="lac"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["lac"] == ["abcde", "fghij"]

    async def test_empty_file_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.txt")
            Path(fpath).write_text("", encoding="utf-8")
            with Tapestry() as t:
                _LoadAndChunk(
                    source=fpath,
                    chunk_size=100,
                    _config=KnotConfig(id="lac"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["lac"] == []

    async def test_rejects_empty_source(self) -> None:
        with Tapestry() as t:
            _LoadAndChunk(
                source="",
                chunk_size=10,
                _config=KnotConfig(id="lac"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_zero_chunk_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello", encoding="utf-8")
            with Tapestry() as t:
                _LoadAndChunk(
                    source=fpath,
                    chunk_size=0,
                    _config=KnotConfig(id="lac"),
                )
            result = await t.run(RunRequest())
            assert not result.succeeded
