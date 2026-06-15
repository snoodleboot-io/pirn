"""Unit tests for :class:`_TranslationLoadAndChunk`."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.document_processing._translation_load_and_chunk import (
    _TranslationLoadAndChunk,
)
from pirn.tapestry import Tapestry


class TestTranslationLoadAndChunkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("abcde12345", encoding="utf-8")
            with Tapestry() as t:
                _TranslationLoadAndChunk(
                    source=fpath,
                    chunk_size=5,
                    _config=KnotConfig(id="tlac"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["tlac"] == ["abcde", "12345"]

    async def test_empty_file_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.txt")
            Path(fpath).write_text("", encoding="utf-8")
            with Tapestry() as t:
                _TranslationLoadAndChunk(
                    source=fpath,
                    chunk_size=10,
                    _config=KnotConfig(id="tlac"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["tlac"] == []

    async def test_rejects_empty_source(self) -> None:
        with Tapestry() as t:
            _TranslationLoadAndChunk(
                source="",
                chunk_size=10,
                _config=KnotConfig(id="tlac"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_empty_source(self) -> None:
        with Tapestry():
            k = _TranslationLoadAndChunk.__new__(_TranslationLoadAndChunk)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(source="", chunk_size=10)

    async def test_process_reads_file_and_chunks_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.txt")
            Path(fpath).write_text("hellworld", encoding="utf-8")
            with Tapestry():
                k = _TranslationLoadAndChunk.__new__(_TranslationLoadAndChunk)
                object.__setattr__(k, "_config", KnotConfig(id="x"))
            chunks = await k.process(source=fpath, chunk_size=5)
        assert chunks == ["hellw", "orld"]
