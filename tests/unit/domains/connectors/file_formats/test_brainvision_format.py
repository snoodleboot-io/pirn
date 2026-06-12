"""Tests for :class:`BrainVisionFormat` — BrainVision EEG format."""

from __future__ import annotations

import io
import unittest
import zipfile
from collections.abc import Mapping
from typing import Any
from unittest.mock import patch

import numpy as np

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.brainvision_format import (
    BrainVisionFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel_records(
    n_channels: int = 3, n_samples: int = 100, sfreq: float = 1000.0
) -> list[dict[str, Any]]:
    records = []
    for idx in range(n_channels):
        arr = np.linspace(-50.0, 50.0, n_samples)
        records.append({
            "channel_index": idx,
            "channel_name": f"Cz{idx+1}",
            "sample_rate": sfreq,
            "n_samples": n_samples,
            "data": arr.astype(np.float64).tobytes(),
        })
    return records


async def _decode_bytes(
    fmt: BrainVisionFormat, payload: bytes
) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


def _make_zip_bundle(
    n_channels: int = 2, n_samples: int = 50, sfreq: float = 500.0
) -> bytes:
    """Build a minimal BrainVision zip bundle for testing the fallback decoder."""
    sampling_interval = int(1_000_000 / sfreq)
    vhdr = (
        "Brain Vision Data Exchange Header File Version 1.0\n"
        "\n"
        "[Common Infos]\n"
        "Codepage=UTF-8\n"
        "DataFile=recording.eeg\n"
        "MarkerFile=recording.vmrk\n"
        "DataFormat=BINARY\n"
        "DataOrientation=MULTIPLEXED\n"
        f"NumberOfChannels={n_channels}\n"
        f"SamplingInterval={sampling_interval}\n"
        "\n"
        "[Binary Infos]\n"
        "BinaryFormat=IEEE_FLOAT_32\n"
        "\n"
        "[Channel Infos]\n"
    )
    for idx in range(n_channels):
        vhdr += f"Ch{idx+1}=Chan{idx+1},,1,µV\n"

    vmrk = (
        "Brain Vision Data Exchange Marker File, Version 1.0\n"
        "\n"
        "[Common Infos]\n"
        "Codepage=UTF-8\n"
        "DataFile=recording.eeg\n"
        "\n"
        "[Marker Infos]\n"
    )

    # Build MULTIPLEXED float32 data
    data = np.random.uniform(-10, 10, (n_channels, n_samples)).astype(np.float32)
    eeg_bytes = data.T.tobytes()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("recording.vhdr", vhdr)
        zf.writestr("recording.vmrk", vmrk)
        zf.writestr("recording.eeg", eeg_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestBrainVisionFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(BrainVisionFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert BrainVisionFormat().streaming is False

    def test_name(self) -> None:
        assert BrainVisionFormat().name == "brainvision"

    def test_phi_header_fields_is_frozenset(self) -> None:
        assert isinstance(BrainVisionFormat._phi_header_fields, frozenset)


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestBrainVisionFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    def test_phi_fields_defined(self) -> None:
        phi = BrainVisionFormat._phi_header_fields
        assert "SubjectName" in phi
        assert "SubjectID" in phi
        assert "InstitutionName" in phi

    async def test_decoded_records_have_no_phi_keys(self) -> None:
        payload = _make_zip_bundle(n_channels=2, n_samples=50)
        records = await _decode_bytes(BrainVisionFormat(), payload)
        phi_keys = {"subjectname", "subjectid", "institutionname"}
        for rec in records:
            for key in rec:
                assert key.lower() not in phi_keys

    async def test_decoded_record_shape(self) -> None:
        payload = _make_zip_bundle(n_channels=1, n_samples=20)
        records = await _decode_bytes(BrainVisionFormat(), payload)
        assert len(records) == 1
        rec = records[0]
        for key in ("channel_index", "channel_name", "sample_rate", "n_samples", "data"):
            assert key in rec


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestBrainVisionFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_channel(self) -> None:
        records = _make_channel_records(n_channels=1, n_samples=80)
        fmt = BrainVisionFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 1
        assert decoded[0]["channel_index"] == 0
        assert decoded[0]["channel_name"] == "Cz1"
        assert decoded[0]["n_samples"] == 80

    async def test_round_trip_multi_channel(self) -> None:
        records = _make_channel_records(n_channels=4, n_samples=64)
        fmt = BrainVisionFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 4
        for idx, rec in enumerate(decoded):
            assert rec["channel_index"] == idx


# ---------------------------------------------------------------------------
# Fallback path (no mne)
# ---------------------------------------------------------------------------

class TestBrainVisionFormatFallback(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_decodes_bundle(self) -> None:
        payload = _make_zip_bundle(n_channels=2, n_samples=40, sfreq=250.0)
        fmt = BrainVisionFormat()
        # Force fallback by hiding mne
        with patch.dict("sys.modules", {"mne": None}):
            decoded = await _decode_bytes(fmt, payload)
        assert len(decoded) == 2
        for idx, rec in enumerate(decoded):
            assert rec["channel_index"] == idx
            assert rec["n_samples"] == 40

    async def test_fallback_channel_names(self) -> None:
        payload = _make_zip_bundle(n_channels=3, n_samples=20)
        fmt = BrainVisionFormat()
        with patch.dict("sys.modules", {"mne": None}):
            decoded = await _decode_bytes(fmt, payload)
        ch_names = [r["channel_name"] for r in decoded]
        assert ch_names == ["Chan1", "Chan2", "Chan3"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TestBrainVisionFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_raises_value_error(self) -> None:
        fmt = BrainVisionFormat()

        async def _empty():
            return
            yield

        with self.assertRaisesRegex(ValueError, "empty"):
            async for _ in await fmt.write(_empty()):
                pass

    async def test_decode_invalid_zip_raises(self) -> None:
        fmt = BrainVisionFormat()

        async def _iter():
            yield b"this is not a zip file at all"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency (mne) — format still works via fallback
# ---------------------------------------------------------------------------

class TestBrainVisionFormatMissingDep(unittest.IsolatedAsyncioTestCase):
    async def test_works_without_mne_via_fallback(self) -> None:
        """BrainVisionFormat must not raise ImportError when mne is absent."""
        payload = _make_zip_bundle(n_channels=1, n_samples=10)
        fmt = BrainVisionFormat()
        with patch.dict("sys.modules", {"mne": None}):
            decoded = await _decode_bytes(fmt, payload)
        assert len(decoded) == 1
