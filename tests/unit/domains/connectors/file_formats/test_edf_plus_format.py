"""Tests for :class:`EdfPlusFormat` — EDF+ biosignal format with annotations."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any
from unittest.mock import patch

import numpy as np

try:
    import pyedflib  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyedflib not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.edf_format import EdfFormat
from pirn.connectors.file_formats.edf_plus_format import EdfPlusFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal_records(
    n_channels: int = 2, n_samples: int = 256
) -> list[dict[str, Any]]:
    records = []
    for idx in range(n_channels):
        arr = np.linspace(-10.0, 10.0, n_samples)
        records.append({
            "signal_index": idx,
            "label": f"EEG{idx+1}",
            "sample_rate": 256,
            "n_samples": n_samples,
            "physical_min": -100.0,
            "physical_max": 100.0,
            "data": arr.astype(np.float64).tobytes(),
        })
    return records


async def _decode_bytes(
    fmt: EdfPlusFormat, payload: bytes
) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestEdfPlusFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(EdfPlusFormat(), BatchFileFormat)

    def test_is_edf_format_subclass(self) -> None:
        assert isinstance(EdfPlusFormat(), EdfFormat)

    def test_streaming_false(self) -> None:
        assert EdfPlusFormat().streaming is False

    def test_name(self) -> None:
        assert EdfPlusFormat().name == "edf+"

    def test_inherits_phi_header_fields(self) -> None:
        assert "patientname" in EdfPlusFormat._phi_header_fields


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestEdfPlusFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    def test_phi_fields_inherited(self) -> None:
        phi = EdfPlusFormat._phi_header_fields
        assert "patientname" in phi
        assert "patientcode" in phi
        assert "birthdate" in phi
        assert "admincode" in phi

    async def test_decoded_signal_records_have_no_phi_keys(self) -> None:
        records = _make_signal_records(n_channels=1)
        fmt = EdfPlusFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await _decode_bytes(fmt, payload)
        phi_keys = {"patientname", "patientcode", "birthdate", "admincode"}
        signal_records = [r for r in decoded if "_edfplus_annotations" not in r]
        for rec in signal_records:
            for key in rec:
                assert key.lower() not in phi_keys


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestEdfPlusFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_signals_only(self) -> None:
        records = _make_signal_records(n_channels=2, n_samples=256)
        fmt = EdfPlusFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        signal_decoded = [r for r in decoded if "_edfplus_annotations" not in r]
        assert len(signal_decoded) == 2
        for idx, rec in enumerate(signal_decoded):
            assert rec["signal_index"] == idx
            assert rec["label"] == f"EEG{idx+1}"

    async def test_round_trip_with_annotations(self) -> None:
        records = _make_signal_records(n_channels=1, n_samples=256)
        annotation_record = {
            "_edfplus_annotations": [
                {"onset": 1.0, "duration": 0.5, "text": "stimulus"},
                {"onset": 2.0, "duration": -1.0, "text": "response"},
            ]
        }
        all_records = [*records, annotation_record]
        fmt = EdfPlusFormat()
        payload = await FormatRoundTrip.encode(fmt, all_records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        signal_decoded = [r for r in decoded if "_edfplus_annotations" not in r]
        assert len(signal_decoded) == 1


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TestEdfPlusFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_raises_value_error(self) -> None:
        fmt = EdfPlusFormat()

        async def _empty():
            return
            yield

        with self.assertRaisesRegex(ValueError, "empty"):
            async for _ in await fmt.write(_empty()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestEdfPlusFormatMissingDep(unittest.TestCase):
    def test_load_pyedflib_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"pyedflib": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                EdfPlusFormat._load_pyedflib()
