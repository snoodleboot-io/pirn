"""Round-trip and validation tests for :class:`LasFormat`."""

from __future__ import annotations

import unittest

try:
    import lasio  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lasio not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.las_format import LasFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _minimal_las_bytes() -> bytes:
    return b"""~VERSION ---
 VERS. 2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0
 WRAP. NO  : ONE LINE PER DEPTH STEP
~WELL ---
 WELL. Test Well : Well name
~CURVE ---
 DEPT .M    : Depth
 GR   .GAPI : Gamma Ray
 NPHI .V/V  : Neutron Porosity
~DATA ---
 100.0  50.0  0.25
 101.0  55.5  0.22
 102.0  60.1  0.19
"""


def _single_record() -> dict:
    return {
        "curves": ["DEPT", "GR"],
        "data": [[100.0, 50.0], [101.0, 55.5], [102.0, 60.0]],
        "metadata": {},
    }


def _two_curve_record() -> dict:
    return {
        "curves": ["DEPT", "GR", "RHOB"],
        "data": [[0.0, 30.0, 2.35], [1.0, 45.0, 2.40]],
        "metadata": {},
    }


class TestLasFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert LasFormat().name == "las"

    def test_streaming_false(self) -> None:
        assert LasFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(LasFormat(), BatchFileFormat)


class TestLasFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_record(self) -> None:
        fmt = LasFormat()
        record = _single_record()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["curves"] == record["curves"]
        for orig_row, dec_row in zip(
            record["data"], decoded[0]["data"], strict=False
        ):
            for o, d in zip(orig_row, dec_row, strict=False):
                assert abs(o - d) < 1e-4

    async def test_round_trip_multi_curve(self) -> None:
        fmt = LasFormat()
        record = _two_curve_record()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["curves"] == record["curves"]

    async def test_decode_minimal_las_bytes(self) -> None:
        fmt = LasFormat()

        async def _byte_iter():
            yield _minimal_las_bytes()

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert len(records) == 1
        assert "DEPT" in records[0]["curves"]


class TestLasFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_raises(self) -> None:
        fmt = LasFormat()
        with self.assertRaisesRegex(ValueError, "empty"):
            await fmt._encode_full([])


class TestLasFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        import unittest.mock
        fmt = LasFormat()
        with unittest.mock.patch.dict("sys.modules", {"lasio": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_lasio()
