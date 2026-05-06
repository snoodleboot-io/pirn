"""Unit tests for :class:`BandpassFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.bandpass_filter import BandpassFilter
from pirn.domains.health.types.signal_frame import SignalFrame


_CFG = KnotConfig(id="b")
_SIGNAL = SignalFrame(signal_id="s")
_KNOT = BandpassFilter(signal=_SIGNAL, low_hz=1.0, high_hz=40.0, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", low_hz=1.0, high_hz=40.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive_low(self) -> None:
        with self.assertRaisesRegex(ValueError, "low_hz"):
            await _KNOT.process(signal=_SIGNAL, low_hz=0.0, high_hz=40.0)

    async def test_rejects_low_ge_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            await _KNOT.process(signal=_SIGNAL, low_hz=40.0, high_hz=10.0)

    async def test_returns_signal_frame(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, low_hz=1.0, high_hz=40.0)
        assert isinstance(out, SignalFrame)
