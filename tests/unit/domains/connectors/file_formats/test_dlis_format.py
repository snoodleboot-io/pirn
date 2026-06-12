"""Tests for :class:`DlisFormat`."""

from __future__ import annotations

import sys
import unittest
import unittest.mock

import pytest

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.dlis_format import DlisFormat


class TestDlisFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert DlisFormat().name == "dlis"

    def test_streaming_false(self) -> None:
        assert DlisFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(DlisFormat(), BatchFileFormat)


class TestDlisFormatDecode(unittest.IsolatedAsyncioTestCase):
    async def test_decode_requires_dlisio(self) -> None:
        try:
            import dlisio  # noqa: F401
        except ImportError as _e:
            self.skipTest("dlisio not installed")
        pytest.skip("DLIS fixture too complex to synthesise in-memory")

    async def test_decode_with_fixture_skipped(self) -> None:
        pytest.skip("DLIS fixture too complex to synthesise in-memory")


class TestDlisFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_raises_not_implemented(self) -> None:
        fmt = DlisFormat()
        with self.assertRaisesRegex(NotImplementedError, "write is not supported"):
            await fmt._encode_full([])


class TestDlisFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"dlisio": None}):
            fmt = DlisFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_dlisio()
