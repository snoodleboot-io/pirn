"""Unit tests for :class:`PowerSpectrumEstimator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.power_spectrum_estimator import (
    PowerSpectrumEstimator,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="p")
_SIGNAL = SignalPayload(
    metadata=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = PowerSpectrumEstimator(signal=_SIGNAL, method="welch", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="x", method="welch")  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, method="bogus")

    async def test_returns_band_mapping(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, method="welch")
        assert isinstance(out, Mapping)
        assert "alpha" in out
