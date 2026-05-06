"""Unit tests for :class:`NotchFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.notch_filter import NotchFilter
from pirn.domains.health.types.signal_frame import SignalFrame


_CFG = KnotConfig(id="n")
_SIGNAL = SignalFrame(signal_id="s")
_KNOT = NotchFilter(signal=_SIGNAL, notch_hz=60.0, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", notch_hz=60.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, notch_hz=0.0)

    async def test_returns_signal_frame(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, notch_hz=60.0)
        assert isinstance(out, SignalFrame)
