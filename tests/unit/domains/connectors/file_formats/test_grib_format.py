"""Round-trip and validation tests for :class:`GribFormat`."""

from __future__ import annotations
import unittest

import pytest

try:
    import cfgrib
except ImportError as _e:
    raise unittest.SkipTest("cfgrib not installed") from _e
try:
    import eccodes
except ImportError as _e:
    raise unittest.SkipTest("eccodes not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.grib_format import GribFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_grib_payload() -> bytes:
    """Return a minimal GRIB2 file as bytes using eccodes."""
    import eccodes
    import tempfile
    import os
    import io

    buf = io.BytesIO()
    # Create a minimal GRIB2 sample (surface temperature)
    sample_id = eccodes.codes_grib_new_from_samples("regular_ll_pl_grib2")
    try:
        eccodes.codes_set(sample_id, "shortName", "t")
        eccodes.codes_set(sample_id, "typeOfLevel", "isobaricInhPa")
        eccodes.codes_set(sample_id, "level", 500)
        eccodes.codes_write(sample_id, buf)
    finally:
        eccodes.codes_release(sample_id)
    return buf.getvalue()


class TestGribFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert GribFormat().name == "grib"

    def test_streaming_false(self) -> None:
        assert GribFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(GribFormat(), BatchFileFormat)


class TestGribFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_encode_raises_not_implemented(self) -> None:
        fmt = GribFormat()
        with self.assertRaisesRegex(NotImplementedError, "GribFormat"):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "shortName": "t",
                        "name": "Temperature",
                        "typeOfLevel": "isobaricInhPa",
                        "level": 500,
                        "stepRange": "0",
                        "values": b"",
                    }
                ],
            )

    async def test_decode_structure(self) -> None:
        try:
            import eccodes
        except ImportError as _e:
            self.skipTest("eccodes not installed")
        try:
            payload = _make_grib_payload()
        except Exception:
            pytest.skip("eccodes sample files not available in this environment")
        fmt = GribFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        first = records[0]
        assert "shortName" in first
        assert "name" in first
        assert "typeOfLevel" in first
        assert "level" in first
        assert "stepRange" in first
        assert "values" in first
        assert isinstance(first["values"], bytes)


class TestGribFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_empty_bytes_yields_no_records(self) -> None:
        fmt = GribFormat()

        async def _empty_iter():
            yield b""

        record_iter = await fmt.read(_empty_iter())
        records = [r async for r in record_iter]
        assert records == []


class TestGribFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        # TODO(unittest-migrate): replace 'monkeypatch' built-in fixture — use unittest.mock.patch / assertLogs
        import builtins

        real_import = builtins.__import__

        def _block_cfgrib(name: str, *args: object, **kwargs: object) -> object:
            if name in ("cfgrib", "eccodes"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_cfgrib)
        with self.assertRaisesRegex(ImportError, "pirn\\[weather\\]"):
            GribFormat._load_cfgrib_eccodes()
