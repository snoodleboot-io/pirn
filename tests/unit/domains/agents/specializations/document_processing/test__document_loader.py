"""Unit tests for :class:`_DocumentLoader`."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._document_loader import (
    _DocumentLoader,
)
from pirn.tapestry import Tapestry


class TestDocumentLoaderConstruction(unittest.TestCase):
    def test_rejects_non_positive_max_bytes(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                _DocumentLoader(
                    source="file.txt",
                    allowed_root="/tmp",
                    max_bytes=0,
                    _config=KnotConfig(id="dl"),
                )


class TestDocumentLoaderLocalFile(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_within_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello world", encoding="utf-8")
            with Tapestry() as t:
                _DocumentLoader(
                    source=fpath,
                    allowed_root=tmpdir,
                    _config=KnotConfig(id="dl"),
                )
            result = await t.run(RunRequest())
            assert result.outputs["dl"] == "hello world"

    async def test_rejects_path_outside_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with Tapestry() as t:
                _DocumentLoader(
                    source="/etc/passwd",
                    allowed_root=tmpdir,
                    _config=KnotConfig(id="dl"),
                )
            result = await t.run(RunRequest())
            assert not result.succeeded

    async def test_rejects_nonexistent_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with Tapestry() as t:
                _DocumentLoader(
                    source=os.path.join(tmpdir, "nonexistent.txt"),
                    allowed_root=tmpdir,
                    _config=KnotConfig(id="dl"),
                )
            result = await t.run(RunRequest())
            assert not result.succeeded

    async def test_rejects_empty_source(self) -> None:
        with Tapestry() as t:
            _DocumentLoader(
                source="",
                allowed_root="/tmp",
                _config=KnotConfig(id="dl"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_no_allowed_root_raises_for_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("x", encoding="utf-8")
            with Tapestry() as t:
                _DocumentLoader(
                    source=fpath,
                    _config=KnotConfig(id="dl"),
                )
            result = await t.run(RunRequest())
            assert not result.succeeded

    async def test_rejects_unsupported_scheme(self) -> None:
        with Tapestry() as t:
            _DocumentLoader(
                source="ftp://example.com/file",
                _config=KnotConfig(id="dl"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
