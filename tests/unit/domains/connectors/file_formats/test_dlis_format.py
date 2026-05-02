"""Tests for :class:`DlisFormat`."""

from __future__ import annotations

import pytest

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.dlis_format import DlisFormat


class TestDlisFormatConstruction:
    def test_name(self) -> None:
        assert DlisFormat().name == "dlis"

    def test_streaming_false(self) -> None:
        assert DlisFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(DlisFormat(), BatchFileFormat)


class TestDlisFormatDecode:
    @pytest.mark.asyncio
    async def test_decode_requires_dlisio(self) -> None:
        dlisio = pytest.importorskip("dlisio")  # noqa: F841
        pytest.skip("DLIS fixture too complex to synthesise in-memory")

    @pytest.mark.asyncio
    async def test_decode_with_fixture_skipped(self) -> None:
        pytest.skip("DLIS fixture too complex to synthesise in-memory")


class TestDlisFormatErrors:
    @pytest.mark.asyncio
    async def test_encode_raises_not_implemented(self) -> None:
        fmt = DlisFormat()
        with pytest.raises(NotImplementedError, match="write is not supported"):
            await fmt._encode_full([])


class TestDlisFormatMissingDep:
    def test_import_error_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        monkeypatch.setitem(sys.modules, "dlisio", None)  # type: ignore[arg-type]
        fmt = DlisFormat()
        with pytest.raises(ImportError, match="pirn\\[oilgas\\]"):
            fmt._load_dlisio()
