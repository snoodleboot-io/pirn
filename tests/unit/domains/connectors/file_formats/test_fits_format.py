"""Round-trip and validation tests for :class:`FitsFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("astropy")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.fits_format import FitsFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_fits_payload() -> bytes:
    """Return a minimal valid FITS file as bytes."""
    from astropy.io import fits
    import io

    hdul = fits.HDUList([fits.PrimaryHDU()])
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


def _make_fits_payload_with_data() -> bytes:
    """Return a FITS file with image data."""
    from astropy.io import fits
    import io
    import numpy as np

    primary = fits.PrimaryHDU(data=np.array([1, 2, 3], dtype=np.uint8))
    hdul = fits.HDUList([primary])
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


class TestFitsFormatConstruction:
    def test_name(self) -> None:
        assert FitsFormat().name == "fits"

    def test_streaming_false(self) -> None:
        assert FitsFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(FitsFormat(), BatchFileFormat)


class TestFitsFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_decode_empty_primary_hdu(self) -> None:
        payload = _make_fits_payload()
        fmt = FitsFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        first = records[0]
        assert first["hdu_index"] == 0
        assert "hdu_type" in first
        assert "header" in first
        assert isinstance(first["header"], dict)

    @pytest.mark.asyncio
    async def test_decode_hdu_with_data(self) -> None:
        payload = _make_fits_payload_with_data()
        fmt = FitsFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        first = records[0]
        assert first["data"] is not None
        assert isinstance(first["data"], bytes)
        assert len(first["data"]) > 0

    @pytest.mark.asyncio
    async def test_encode_produces_valid_fits(self) -> None:
        from astropy.io import fits
        import io

        records = [
            {
                "hdu_index": 0,
                "hdu_type": "PrimaryHDU",
                "header": {"INSTRUME": "TEST"},
                "data": None,
            }
        ]
        fmt = FitsFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        assert isinstance(payload, bytes)
        assert len(payload) > 0
        # Verify it is a valid FITS file
        with fits.open(io.BytesIO(payload)) as hdul:
            assert len(hdul) >= 1

    @pytest.mark.asyncio
    async def test_encode_then_decode_preserves_hdu_count(self) -> None:
        from astropy.io import fits
        import io
        import numpy as np

        primary = fits.PrimaryHDU(data=np.array([10, 20], dtype=np.uint8))
        hdul = fits.HDUList([primary])
        buf = io.BytesIO()
        hdul.writeto(buf)
        payload = buf.getvalue()

        fmt = FitsFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) == 1
        encoded = await FormatRoundTrip.encode(fmt, records)
        re_decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(re_decoded) == 1


class TestFitsFormatErrors:
    @pytest.mark.asyncio
    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = FitsFormat()

        async def _bad_iter():
            yield b"not a fits file at all !@#$"

        with pytest.raises(Exception):
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestFitsFormatMissingDep:
    def test_import_error_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        import builtins

        real_import = builtins.__import__

        def _block_astropy(name: str, *args: object, **kwargs: object) -> object:
            if name == "astropy.io.fits" or name == "astropy":
                raise ImportError("No module named 'astropy'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_astropy)
        with pytest.raises(ImportError, match="pirn\\[astronomy\\]"):
            FitsFormat._load_fits()
