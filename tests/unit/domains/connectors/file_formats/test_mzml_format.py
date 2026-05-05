"""Tests for :class:`MzmlFormat` — mzML mass spectrometry format."""

from __future__ import annotations

from unittest.mock import patch
import unittest


try:
    import pyteomics
except ImportError as _e:
    raise unittest.SkipTest("pyteomics not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.mzml_format import MzmlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_mzml_bytes() -> bytes:
    """Return a minimal valid mzML document as bytes."""
    import numpy as np

    mz = np.array([100.0, 200.0, 300.0], dtype=np.float64)
    intensity = np.array([1000.0, 500.0, 250.0], dtype=np.float64)
    import base64

    mz_b64 = base64.b64encode(mz.tobytes()).decode("ascii")
    int_b64 = base64.b64encode(intensity.tobytes()).decode("ascii")
    mzml_text = f"""<?xml version="1.0" encoding="utf-8"?>
<mzML xmlns="http://psi.hupo.org/ms/mzml">
  <run>
    <spectrumList count="1">
      <spectrum index="0" id="scan=1" defaultArrayLength="3">
        <cvParam accession="MS:1000511" name="ms level" value="1"/>
        <scanList count="1">
          <scan>
            <cvParam accession="MS:1000016" name="scan start time" value="0.5" unitName="second"/>
          </scan>
        </scanList>
        <binaryDataArrayList count="2">
          <binaryDataArray>
            <cvParam accession="MS:1000514" name="m/z array"/>
            <cvParam accession="MS:1000576" name="no compression"/>
            <cvParam accession="MS:1000514" name="64-bit float"/>
            <binary>{mz_b64}</binary>
          </binaryDataArray>
          <binaryDataArray>
            <cvParam accession="MS:1000515" name="intensity array"/>
            <cvParam accession="MS:1000576" name="no compression"/>
            <cvParam accession="MS:1000515" name="64-bit float"/>
            <binary>{int_b64}</binary>
          </binaryDataArray>
        </binaryDataArrayList>
      </spectrum>
    </spectrumList>
  </run>
</mzML>"""
    return mzml_text.encode("utf-8")


async def _decode_bytes(fmt: MzmlFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestMzmlFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(MzmlFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert MzmlFormat().streaming is False

    def test_name(self) -> None:
        assert MzmlFormat().name == "mzml"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestMzmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_record_shape(self) -> None:
        payload = _make_minimal_mzml_bytes()
        records = await _decode_bytes(MzmlFormat(), payload)
        assert len(records) >= 1
        record = records[0]
        assert "scan_number" in record
        assert "ms_level" in record
        assert "retention_time" in record
        assert "mz_array" in record
        assert "intensity_array" in record

    async def test_decode_arrays_are_bytes(self) -> None:
        payload = _make_minimal_mzml_bytes()
        records = await _decode_bytes(MzmlFormat(), payload)
        assert isinstance(records[0]["mz_array"], bytes)
        assert isinstance(records[0]["intensity_array"], bytes)

    async def test_encode_decode_round_trip(self) -> None:
        import numpy as np

        mz = np.array([100.0, 200.0], dtype=np.float64)
        intensity = np.array([500.0, 300.0], dtype=np.float64)
        records = [
            {
                "scan_number": 1,
                "ms_level": 1,
                "retention_time": 1.5,
                "mz_array": mz.tobytes(),
                "intensity_array": intensity.tobytes(),
            }
        ]
        fmt = MzmlFormat()
        encoded = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(decoded) == 1
        mz_out = np.frombuffer(decoded[0]["mz_array"], dtype=np.float64)
        int_out = np.frombuffer(decoded[0]["intensity_array"], dtype=np.float64)
        assert np.allclose(mz_out, mz)
        assert np.allclose(int_out, intensity)

    async def test_ms_level_preserved(self) -> None:
        payload = _make_minimal_mzml_bytes()
        records = await _decode_bytes(MzmlFormat(), payload)
        assert records[0]["ms_level"] == 1


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestMzmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_non_bytes_mz_array_raises(self) -> None:
        fmt = MzmlFormat()

        async def _records():
            yield {
                "scan_number": 1,
                "ms_level": 1,
                "retention_time": 0.0,
                "mz_array": "not bytes",
                "intensity_array": b"",
            }

        with self.assertRaisesRegex(TypeError, "mz_array"):
            async for _ in await fmt.write(_records()):
                pass

    async def test_invalid_xml_raises(self) -> None:
        fmt = MzmlFormat()

        async def _iter():
            yield b"<not valid mzml"

        with self.assertRaises(Exception):
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency guard
# ---------------------------------------------------------------------------

class TestMzmlFormatMissingDep(unittest.TestCase):
    def test_load_pyteomics_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"pyteomics": None, "pyteomics.mzml": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                MzmlFormat._load_pyteomics_mzml()

    def test_load_lxml_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"lxml": None, "lxml.etree": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                MzmlFormat._load_lxml()
