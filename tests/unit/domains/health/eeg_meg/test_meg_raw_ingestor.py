"""Unit tests for :class:`MEGRawIngestor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.meg_raw_ingestor import MEGRawIngestor
from pirn.domains.health.types.signal_frame import SignalFrame

_CFG = KnotConfig(id="i")
_KNOT = MEGRawIngestor(
    recording_path="x.fif",
    signal_id="sig",
    channel_count=128,
    sample_rate_hz=1000.0,
    samples_per_channel=1024,
    _config=_CFG,
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _KNOT.process(
                recording_path="",
                signal_id="sig",
                channel_count=128,
                sample_rate_hz=1000.0,
                samples_per_channel=1024,
            )

    async def test_rejects_non_positive_channel(self) -> None:
        with self.assertRaisesRegex(ValueError, "channel_count"):
            await _KNOT.process(
                recording_path="x",
                signal_id="sig",
                channel_count=0,
                sample_rate_hz=1000.0,
                samples_per_channel=1024,
            )

    async def test_rejects_non_positive_rate(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
            await _KNOT.process(
                recording_path="x",
                signal_id="sig",
                channel_count=128,
                sample_rate_hz=0.0,
                samples_per_channel=1024,
            )

    async def test_returns_signal_frame(self) -> None:
        out = await _KNOT.process(
            recording_path="x.fif",
            signal_id="sig",
            channel_count=128,
            sample_rate_hz=1000.0,
            samples_per_channel=1024,
        )
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "sig"
