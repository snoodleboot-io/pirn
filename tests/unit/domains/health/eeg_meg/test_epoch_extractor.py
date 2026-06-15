"""Unit tests for :class:`EpochExtractor`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.epoch_extractor import EpochExtractor
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="e")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = EpochExtractor(signal=_SIGNAL, event_times_sec=[1.0], tmin_sec=-0.2, tmax_sec=0.5, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", event_times_sec=[1.0], tmin_sec=-0.2, tmax_sec=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "event_times_sec"):
            await _KNOT.process(signal=_SIGNAL, event_times_sec=42, tmin_sec=-0.2, tmax_sec=0.5)  # type: ignore[arg-type]

    async def test_rejects_tmin_ge_tmax(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            await _KNOT.process(signal=_SIGNAL, event_times_sec=[1.0], tmin_sec=0.5, tmax_sec=0.5)

    async def test_returns_epochs(self) -> None:
        out = await _KNOT.process(
            signal=_SIGNAL,
            event_times_sec=[1.0, 2.0, 3.0],
            tmin_sec=-0.2,
            tmax_sec=0.5,
        )
        assert isinstance(out, tuple)
        assert len(out) == 3
        assert all(isinstance(x, HealthSignalPayload) for x in out)
