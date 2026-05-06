"""Unit tests for :class:`SeizureDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.seizure_detector import SeizureDetector
from pirn.domains.health.types.signal_frame import SignalFrame

_CFG = KnotConfig(id="s")
_SIGNAL = SignalFrame()
_KNOT = SeizureDetector(signal=_SIGNAL, threshold=0.5, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", threshold=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_numeric_threshold(self) -> None:
        with self.assertRaisesRegex(TypeError, "threshold"):
            await _KNOT.process(signal=_SIGNAL, threshold="x")  # type: ignore[arg-type]

    async def test_rejects_negative_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            await _KNOT.process(signal=_SIGNAL, threshold=-1.0)

    async def test_returns_intervals(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, threshold=0.5)
        assert isinstance(out, tuple)
