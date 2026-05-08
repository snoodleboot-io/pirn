"""Unit tests for :class:`SleepStageClassifier`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.sleep_stage_classifier import SleepStageClassifier
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="sc")
_SIGNAL = SignalPayload(
    frame=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = SleepStageClassifier(signal=_SIGNAL, epoch_duration_sec=30, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="not-a-signal", epoch_duration_sec=30)  # type: ignore[arg-type]

    async def test_rejects_non_30_epoch_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "epoch_duration_sec"):
            await _KNOT.process(signal=_SIGNAL, epoch_duration_sec=20)

    async def test_rejects_empty_channels(self) -> None:
        with self.assertRaisesRegex(ValueError, "channels"):
            await _KNOT.process(signal=_SIGNAL, epoch_duration_sec=30, channels=())

    async def test_returns_dict_with_required_keys(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, epoch_duration_sec=30)
        assert isinstance(out, dict)
        assert "stage_labels" in out
        assert "total_epochs" in out
        assert "sleep_efficiency_pct" in out

    async def test_stage_labels_are_valid_stages(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, epoch_duration_sec=30)
        valid_stages = {"W", "N1", "N2", "N3", "REM"}
        for label in out["stage_labels"]:
            assert label in valid_stages
