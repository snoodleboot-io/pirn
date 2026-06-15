"""Unit tests for :class:`SeizureDetector`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_health.eeg_meg.seizure_detector import SeizureDetector
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="s")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = SeizureDetector(signal=_SIGNAL, threshold=0.5, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", threshold=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_numeric_threshold(self) -> None:
        with self.assertRaisesRegex(TypeError, "threshold"):
            await _KNOT.process(signal=_SIGNAL, threshold="x")  # type: ignore[arg-type]

    async def test_rejects_negative_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            await _KNOT.process(signal=_SIGNAL, threshold=-1.0)

    async def test_returns_intervals(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, threshold=0.5)
        assert isinstance(out, (tuple, list))
