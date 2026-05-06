"""Unit tests for :class:`PowerSpectrumEstimator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.power_spectrum_estimator import (
    PowerSpectrumEstimator,
)
from pirn.domains.health.types.signal_frame import SignalFrame

_CFG = KnotConfig(id="p")
_SIGNAL = SignalFrame()
_KNOT = PowerSpectrumEstimator(signal=_SIGNAL, method="welch", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", method="welch")  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, method="bogus")

    async def test_returns_band_mapping(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, method="welch")
        assert isinstance(out, Mapping)
        assert "alpha" in out
