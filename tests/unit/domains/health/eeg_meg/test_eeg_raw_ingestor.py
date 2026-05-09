"""Unit tests for :class:`EEGRawIngestor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.eeg_raw_ingestor import EEGRawIngestor
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="i")
_KNOT = EEGRawIngestor(
    recording_path="x.edf",
    subject_id="S1",
    channel_count=64,
    sample_rate_hz=1000.0,
    duration_sec=120.0,
    _config=_CFG,
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _KNOT.process(
                recording_path="",
                subject_id="S1",
                channel_count=64,
                sample_rate_hz=1000.0,
                duration_sec=120.0,
            )

    async def test_rejects_non_int_channel(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_count"):
            await _KNOT.process(
                recording_path="x",
                subject_id="S1",
                channel_count="x",  # type: ignore[arg-type]
                sample_rate_hz=1000.0,
                duration_sec=120.0,
            )

    async def test_rejects_non_positive_channel(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(
                recording_path="x",
                subject_id="S1",
                channel_count=0,
                sample_rate_hz=1000.0,
                duration_sec=120.0,
            )

    async def test_rejects_non_positive_rate(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(
                recording_path="x",
                subject_id="S1",
                channel_count=64,
                sample_rate_hz=0.0,
                duration_sec=120.0,
            )

    async def test_returns_signal_payload(self) -> None:
        out = await _KNOT.process(
            recording_path="x.edf",
            subject_id="S1",
            channel_count=64,
            sample_rate_hz=1000.0,
            duration_sec=120.0,
        )
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "S1"
        assert out.frame.channel_count == 64
        assert out.data.shape == (64, 120000)
