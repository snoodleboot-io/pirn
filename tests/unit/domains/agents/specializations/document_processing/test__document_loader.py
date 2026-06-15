"""Unit tests for :class:`_DocumentLoader`."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing._document_loader import (
    _DocumentLoader,
)
from pirn.tapestry import Tapestry


def _make_knot(allowed_root: str | None = None) -> _DocumentLoader:
    with Tapestry():
        return _DocumentLoader(
            source="placeholder",
            allowed_root=allowed_root,
            _config=KnotConfig(id="dl"),
        )


class TestDocumentLoaderLocalFile(unittest.IsolatedAsyncioTestCase):
    async def test_reads_file_within_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("hello world", encoding="utf-8")
            k = _make_knot(allowed_root=tmpdir)
            result = await k.process(source=fpath, allowed_root=tmpdir)
            assert result == "hello world"

    async def test_rejects_path_outside_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            k = _make_knot(allowed_root=tmpdir)
            with self.assertRaises(ValueError):
                await k.process(source="/etc/passwd", allowed_root=tmpdir)

    async def test_rejects_nonexistent_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            k = _make_knot(allowed_root=tmpdir)
            with self.assertRaises(ValueError):
                await k.process(source=os.path.join(tmpdir, "nonexistent.txt"), allowed_root=tmpdir)

    async def test_rejects_empty_source(self) -> None:
        k = _make_knot(allowed_root="/tmp")
        with self.assertRaises(TypeError):
            await k.process(source="", allowed_root="/tmp")

    async def test_no_allowed_root_raises_for_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "doc.txt")
            Path(fpath).write_text("x", encoding="utf-8")
            k = _make_knot()
            with self.assertRaises(ValueError):
                await k.process(source=fpath)

    async def test_rejects_unsupported_scheme(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await k.process(source="ftp://example.com/file")

    async def test_rejects_non_positive_max_bytes(self) -> None:
        k = _make_knot(allowed_root="/tmp")
        with self.assertRaises(ValueError):
            await k.process(source="anyfile", allowed_root="/tmp", max_bytes=0)
