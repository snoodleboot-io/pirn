"""Unit tests for :class:`EegNotchFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.eeg_notch_filter import EegNotchFilter
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="n")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = EegNotchFilter(signal=_SIGNAL, notch_hz=60.0, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", notch_hz=60.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, notch_hz=0.0)

    async def test_returns_signal_payload(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, notch_hz=60.0)
        assert isinstance(out, HealthSignalPayload)
