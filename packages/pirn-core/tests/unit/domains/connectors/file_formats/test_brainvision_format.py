"""Tests for :class:`BrainVisionFormat` — BrainVision EEG format.

Decoding requires ``mne``, which is an optional extra of ``pirn-health``, so
these tests stand a fake ``mne`` in ``sys.modules`` that reads the same three
files off disk (PIR-873). The format used to carry a header-only decoder of its
own and fall back to it whenever the import failed — production code that only
existed to keep these tests offline, and which returned raw ADC integers where
``mne`` returns volts, with nothing in the records to say which had run.
"""

from __future__ import annotations

import configparser
import io
import sys
import unittest
import zipfile
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock
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
        records.append(
            {
                "channel_index": idx,
                "channel_name": f"Cz{idx + 1}",
                "sample_rate": sfreq,
                "n_samples": n_samples,
                "data": arr.astype(np.float64).tobytes(),
            }
        )
    return records


async def _decode_bytes(fmt: BrainVisionFormat, payload: bytes) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


class FakeRawBrainVision:
    """The slice of ``mne``'s ``Raw`` that :meth:`_decode_with_mne` reads."""

    def __init__(self, data: Any, sfreq: float, ch_names: list[str]) -> None:
        self._data = data
        self.info: dict[str, Any] = {"sfreq": sfreq, "ch_names": ch_names}

    def get_data(self, return_times: bool = False) -> Any:
        times = np.arange(self._data.shape[1], dtype=np.float64)
        return (self._data, times) if return_times else self._data


def _fake_read_raw_brainvision(
    vhdr_path: str, preload: bool = True, verbose: bool = False
) -> FakeRawBrainVision:
    """Read the bundle the format wrote to disk, the way ``mne`` would.

    Deliberately reads the ``.eeg`` file named by the rewritten header, so the
    test still covers ``_decode_with_mne``'s temp-directory handling and
    ``_rewrite_vhdr_paths``.
    """
    base = Path(vhdr_path).parent
    text = Path(vhdr_path).read_text(encoding="utf-8")
    parser = configparser.ConfigParser(strict=False)
    parser.read_string(
        "\n".join(line for line in text.splitlines() if not line.startswith("Brain Vision"))
    )
    n_channels = int(parser.get("Common Infos", "NumberOfChannels", fallback="0"))
    sfreq = 1_000_000.0 / float(parser.get("Common Infos", "SamplingInterval", fallback="1000"))
    data_file = parser.get("Common Infos", "DataFile", fallback="recording.eeg")
    ch_names = [
        parser.get("Channel Infos", f"ch{idx}", fallback=f"Ch{idx}").split(",")[0].strip()
        for idx in range(1, n_channels + 1)
    ]
    raw = np.frombuffer((base / data_file).read_bytes(), dtype=np.float32)
    n_samples = len(raw) // n_channels if n_channels else 0
    data = raw[: n_samples * n_channels].reshape(n_samples, n_channels).T.astype(np.float64)
    return FakeRawBrainVision(data, sfreq, ch_names)


def _fake_mne() -> mock._patch_dict:
    """Patch ``sys.modules`` so the lazy ``mne`` import resolves to the fake."""
    return mock.patch.dict(
        sys.modules,
        {
            "mne": SimpleNamespace(
                io=SimpleNamespace(read_raw_brainvision=_fake_read_raw_brainvision)
            )
        },
    )


def _make_zip_bundle(n_channels: int = 2, n_samples: int = 50, sfreq: float = 500.0) -> bytes:
    """Build a minimal BrainVision zip bundle."""
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
        vhdr += f"Ch{idx + 1}=Chan{idx + 1},,1,µV\n"

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
        with _fake_mne():
            records = await _decode_bytes(BrainVisionFormat(), payload)
        phi_keys = {"subjectname", "subjectid", "institutionname"}
        for rec in records:
            for key in rec:
                assert key.lower() not in phi_keys

    async def test_decoded_record_shape(self) -> None:
        payload = _make_zip_bundle(n_channels=1, n_samples=20)
        with _fake_mne():
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
        with _fake_mne():
            decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 1
        assert decoded[0]["channel_index"] == 0
        assert decoded[0]["channel_name"] == "Cz1"
        assert decoded[0]["n_samples"] == 80

    async def test_round_trip_multi_channel(self) -> None:
        records = _make_channel_records(n_channels=4, n_samples=64)
        fmt = BrainVisionFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        with _fake_mne():
            decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 4
        for idx, rec in enumerate(decoded):
            assert rec["channel_index"] == idx


# ---------------------------------------------------------------------------
# Decode path
# ---------------------------------------------------------------------------


class TestBrainVisionFormatDecode(unittest.IsolatedAsyncioTestCase):
    async def test_decodes_bundle(self) -> None:
        payload = _make_zip_bundle(n_channels=2, n_samples=40, sfreq=250.0)
        fmt = BrainVisionFormat()
        with _fake_mne():
            decoded = await _decode_bytes(fmt, payload)
        assert len(decoded) == 2
        for idx, rec in enumerate(decoded):
            assert rec["channel_index"] == idx
            assert rec["n_samples"] == 40
            assert rec["sample_rate"] == 250.0

    async def test_channel_names_come_from_the_header(self) -> None:
        payload = _make_zip_bundle(n_channels=3, n_samples=20)
        fmt = BrainVisionFormat()
        with _fake_mne():
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
# Missing dependency (mne)
# ---------------------------------------------------------------------------


class TestBrainVisionFormatMissingDep(unittest.IsolatedAsyncioTestCase):
    async def test_decode_without_mne_raises_the_install_hint(self) -> None:
        """No second decoder: a missing mne is reported, not silently replaced (PIR-873)."""
        payload = _make_zip_bundle(n_channels=1, n_samples=10)
        fmt = BrainVisionFormat()
        with patch.dict("sys.modules", {"mne": None}):
            with self.assertRaisesRegex(ImportError, r'pip install "pirn-health\[health\]"'):
                await _decode_bytes(fmt, payload)

    async def test_encode_needs_no_mne(self) -> None:
        """Encoding is pure numpy, so it keeps working without the extra."""
        records = _make_channel_records(n_channels=2, n_samples=16)
        with patch.dict("sys.modules", {"mne": None}):
            payload = await FormatRoundTrip.encode(BrainVisionFormat(), records)
        assert payload[:2] == b"PK"
