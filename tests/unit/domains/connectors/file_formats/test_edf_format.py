"""Tests for :class:`EdfFormat` — EDF biosignal format."""

from __future__ import annotations

import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np

try:
    import pyedflib  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyedflib not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.edf_format import EdfFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_edf_bytes(n_channels: int = 2, n_samples: int = 100) -> bytes:
    import pyedflib

    with tempfile.NamedTemporaryFile(suffix=".edf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with pyedflib.EdfWriter(tmp_path, n_channels) as writer:
            headers = []
            signals = []
            for idx in range(n_channels):
                headers.append({
                    "label": f"EEG{idx+1}",
                    "dimension": "uV",
                    "sample_frequency": 256,
                    "physical_min": -100.0,
                    "physical_max": 100.0,
                    "digital_min": -32768,
                    "digital_max": 32767,
                    "transducer": "",
                    "prefilter": "",
                })
                signals.append(np.random.uniform(-50, 50, n_samples))
            writer.setSignalHeaders(headers)
            writer.writeSamples(signals)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _decode_bytes(fmt: EdfFormat, payload: bytes) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


def _make_signal_records(n_channels: int = 2, n_samples: int = 256) -> list[dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestEdfFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(EdfFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert EdfFormat().streaming is False

    def test_name(self) -> None:
        assert EdfFormat().name == "edf"

    def test_phi_header_fields_is_frozenset(self) -> None:
        assert isinstance(EdfFormat._phi_header_fields, frozenset)


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestEdfFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    def test_phi_fields_defined(self) -> None:
        phi = EdfFormat._phi_header_fields
        assert "patientname" in phi
        assert "patientcode" in phi
        assert "birthdate" in phi
        assert "admincode" in phi

    async def test_decoded_records_have_no_phi_keys(self) -> None:
        payload = _make_minimal_edf_bytes()
        records = await _decode_bytes(EdfFormat(), payload)
        phi_keys = {"patientname", "patientcode", "birthdate", "admincode"}
        for rec in records:
            for key in rec:
                assert key.lower() not in phi_keys, (
                    f"PHI key {key!r} found in decoded record"
                )

    async def test_decoded_record_shape(self) -> None:
        payload = _make_minimal_edf_bytes(n_channels=1)
        records = await _decode_bytes(EdfFormat(), payload)
        assert len(records) == 1
        rec = records[0]
        for key in ("signal_index", "label", "sample_rate", "n_samples",
                    "physical_min", "physical_max", "data"):
            assert key in rec, f"Missing key {key!r}"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestEdfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_channel(self) -> None:
        # EDF stores one data-record per second; n_samples must equal
        # sample_rate so the record exactly fills one second.
        sample_rate = 128
        n_samples = sample_rate
        arr = np.linspace(-5.0, 5.0, n_samples)
        records = [
            {
                "signal_index": 0,
                "label": "EEG1",
                "sample_rate": sample_rate,
                "n_samples": n_samples,
                "physical_min": -100.0,
                "physical_max": 100.0,
                "data": arr.astype(np.float64).tobytes(),
            }
        ]
        fmt = EdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 1
        assert decoded[0]["signal_index"] == 0
        assert decoded[0]["label"] == "EEG1"
        assert decoded[0]["sample_rate"] == sample_rate
        assert decoded[0]["n_samples"] == n_samples

        out_arr = np.frombuffer(decoded[0]["data"], dtype=np.float64)
        assert len(out_arr) == n_samples

    async def test_round_trip_multi_channel(self) -> None:
        records = _make_signal_records(n_channels=3, n_samples=256)
        fmt = EdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 3
        for idx, rec in enumerate(decoded):
            assert rec["signal_index"] == idx
            assert rec["label"] == f"EEG{idx+1}"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TestEdfFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_raises_value_error(self) -> None:
        fmt = EdfFormat()

        async def _empty():
            return
            yield

        with self.assertRaisesRegex(ValueError, "empty"):
            async for _ in await fmt.write(_empty()):
                pass

    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = EdfFormat()

        async def _iter():
            yield b"this is definitely not an edf file"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestEdfFormatMissingDep(unittest.TestCase):
    def test_load_pyedflib_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"pyedflib": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                EdfFormat._load_pyedflib()
