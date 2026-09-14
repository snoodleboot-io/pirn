"""Unit tests for :class:`SleepStageClassifier`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.eeg_meg.sleep_stage_classifier import SleepStageClassifier
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="sc")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(
        signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512
    ),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = SleepStageClassifier(signal=_SIGNAL, epoch_duration_sec=30, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
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

    async def test_full_epochs_integrate_band_power(self) -> None:
        # Arrange: two full 30 s epochs, a 2 Hz (delta) epoch then a 10 Hz (alpha)
        # epoch, so the welch + numpy.trapezoid band-power path runs for real.
        fs = 100.0
        t = np.arange(int(fs * 30)) / fs
        delta_epoch = np.sin(2 * np.pi * 2.0 * t)
        alpha_epoch = np.sin(2 * np.pi * 10.0 * t)
        channel = np.concatenate([delta_epoch, alpha_epoch])
        signal = HealthSignalPayload(
            metadata=HealthSignalFrame(
                signal_id="psg",
                channel_count=1,
                sample_rate_hz=fs,
                samples_per_channel=channel.size,
            ),
            data=channel[np.newaxis, :],
        )

        # Act
        out = await _KNOT.process(signal=signal, epoch_duration_sec=30)

        # Assert
        assert out["stage_labels"] == ["N3", "W"]
        assert out["total_epochs"] == 2
        assert out["sleep_efficiency_pct"] == 50.0

    async def test_raises_install_hint_without_scipy(self) -> None:
        signal = HealthSignalPayload(
            metadata=HealthSignalFrame(
                signal_id="psg", channel_count=1, sample_rate_hz=100.0, samples_per_channel=3000
            ),
            data=np.zeros((1, 3000)),
        )
        with patch.dict(sys.modules, {"scipy.signal": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-health\[health\]"):
                await _KNOT.process(signal=signal, epoch_duration_sec=30)
