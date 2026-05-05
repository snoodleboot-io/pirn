"""Unit tests for :class:`_QALoadAndChunk`."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._qa_load_and_chunk import (
    _QALoadAndChunk,
)
from pirn.tapestry import Tapestry


class TestQALoadAndChunkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello world!", encoding="utf-8")
            with Tapestry() as t:
                _QALoadAndChunk(
                    source=fpath,
                    chunk_size=6,
                    _config=KnotConfig(id="qa_lac"),
                )
            result = await t.run(RunRequest())
            chunks = result.outputs["qa_lac"]
            assert isinstance(chunks, list)
            assert "".join(chunks) == "hello world!"

    async def test_empty_file_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.txt")
            Path(fpath).write_text("", encoding="utf-8")
            with Tapestry() as t:
                _QALoadAndChunk(
                    source=fpath,
                    chunk_size=100,
                    _config=KnotConfig(id="qa_lac"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["qa_lac"] == []
