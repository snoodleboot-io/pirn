"""Tests for :class:`BdfFormat` — BDF biosignal format."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

pytest.importorskip("pyedflib")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.bdf_format import BdfFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_bdf_bytes(n_channels: int = 2, n_samples: int = 100) -> bytes:
    import pyedflib

    with tempfile.NamedTemporaryFile(suffix=".bdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with pyedflib.EdfWriter(
            tmp_path, n_channels, file_type=pyedflib.FILETYPE_BDF
        ) as writer:
            headers = []
            signals = []
            for idx in range(n_channels):
                headers.append({
                    "label": f"EEG{idx+1}",
                    "dimension": "uV",
                    "sample_frequency": 512,
                    "physical_min": -8388608.0,
                    "physical_max": 8388607.0,
                    "digital_min": -8388608,
                    "digital_max": 8388607,
                    "transducer": "",
                    "prefilter": "",
                })
                signals.append(np.random.uniform(-1000, 1000, n_samples))
            writer.setSignalHeaders(headers)
            writer.writeSamples(signals)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _decode_bytes(fmt: BdfFormat, payload: bytes) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


def _make_signal_records(n_channels: int = 2, n_samples: int = 512) -> list[dict[str, Any]]:
    records = []
    for idx in range(n_channels):
        arr = np.linspace(-500.0, 500.0, n_samples)
        records.append({
            "signal_index": idx,
            "label": f"EEG{idx+1}",
            "sample_rate": 512,
            "n_samples": n_samples,
            "physical_min": -8000000.0,
            "physical_max": 8000000.0,
            "data": arr.astype(np.float64).tobytes(),
        })
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestBdfFormatConstruction:
    def test_is_batch_format(self) -> None:
        assert isinstance(BdfFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert BdfFormat().streaming is False

    def test_name(self) -> None:
        assert BdfFormat().name == "bdf"

    def test_phi_header_fields_is_frozenset(self) -> None:
        assert isinstance(BdfFormat._phi_header_fields, frozenset)


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestBdfFormatPhiSanitisation:
    def test_phi_fields_defined(self) -> None:
        phi = BdfFormat._phi_header_fields
        assert "patientname" in phi
        assert "patientcode" in phi
        assert "birthdate" in phi
        assert "admincode" in phi

    @pytest.mark.asyncio
    async def test_decoded_records_have_no_phi_keys(self) -> None:
        payload = _make_minimal_bdf_bytes()
        records = await _decode_bytes(BdfFormat(), payload)
        phi_keys = {"patientname", "patientcode", "birthdate", "admincode"}
        for rec in records:
            for key in rec:
                assert key.lower() not in phi_keys

    @pytest.mark.asyncio
    async def test_decoded_record_shape(self) -> None:
        payload = _make_minimal_bdf_bytes(n_channels=1)
        records = await _decode_bytes(BdfFormat(), payload)
        assert len(records) == 1
        rec = records[0]
        for key in ("signal_index", "label", "sample_rate", "n_samples",
                    "physical_min", "physical_max", "data"):
            assert key in rec


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestBdfFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_single_channel(self) -> None:
        # BDF (like EDF) stores one data-record per second; n_samples
        # must equal sample_rate so the record fills exactly one second.
        sample_rate = 512
        n_samples = sample_rate
        arr = np.linspace(-1000.0, 1000.0, n_samples)
        records = [
            {
                "signal_index": 0,
                "label": "EEG1",
                "sample_rate": sample_rate,
                "n_samples": n_samples,
                "physical_min": -8000000.0,
                "physical_max": 8000000.0,
                "data": arr.astype(np.float64).tobytes(),
            }
        ]
        fmt = BdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 1
        assert decoded[0]["signal_index"] == 0
        assert decoded[0]["label"] == "EEG1"
        assert decoded[0]["sample_rate"] == sample_rate
        assert decoded[0]["n_samples"] == n_samples

    @pytest.mark.asyncio
    async def test_round_trip_multi_channel(self) -> None:
        records = _make_signal_records(n_channels=4, n_samples=512)
        fmt = BdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 4
        for idx, rec in enumerate(decoded):
            assert rec["signal_index"] == idx
            assert rec["label"] == f"EEG{idx+1}"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TestBdfFormatErrors:
    @pytest.mark.asyncio
    async def test_encode_empty_raises_value_error(self) -> None:
        fmt = BdfFormat()

        async def _empty():
            return
            yield

        with pytest.raises(ValueError, match="empty"):
            async for _ in await fmt.write(_empty()):
                pass

    @pytest.mark.asyncio
    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = BdfFormat()

        async def _iter():
            yield b"this is not a bdf file"

        with pytest.raises(Exception):
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestBdfFormatMissingDep:
    def test_load_pyedflib_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"pyedflib": None}):
            with pytest.raises(ImportError, match="pirn\\[health\\]"):
                BdfFormat._load_pyedflib()
