"""Tests for :class:`ArchiveFileFormat`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.connectors.file_format import FileFormat
from pirn.connectors.file_formats.archive_file_format import ArchiveFileFormat


def _make_inner() -> MagicMock:
    inner = MagicMock(spec=FileFormat)
    inner.name = "json"
    return inner


class TestArchiveFileFormatConstruction(unittest.TestCase):
    def test_valid_tar_construction(self) -> None:
        fmt = ArchiveFileFormat(inner=_make_inner(), archive_type="tar")
        self.assertIsInstance(fmt, ArchiveFileFormat)

    def test_valid_zip_construction(self) -> None:
        fmt = ArchiveFileFormat(inner=_make_inner(), archive_type="zip")
        self.assertIsInstance(fmt, ArchiveFileFormat)

    def test_rejects_non_file_format_inner(self) -> None:
        with self.assertRaises(TypeError):
            ArchiveFileFormat(inner="not-a-format", archive_type="tar")  # type: ignore[arg-type]

    def test_rejects_unknown_archive_type(self) -> None:
        with self.assertRaises(ValueError):
            ArchiveFileFormat(inner=_make_inner(), archive_type="rar")

    def test_name_includes_archive_and_inner(self) -> None:
        fmt = ArchiveFileFormat(inner=_make_inner(), archive_type="tar.gz")
        self.assertIn("tar.gz", fmt.name)
        self.assertIn("json", fmt.name)

    def test_streaming_is_false(self) -> None:
        fmt = ArchiveFileFormat(inner=_make_inner(), archive_type="zip")
        self.assertFalse(fmt.streaming)
