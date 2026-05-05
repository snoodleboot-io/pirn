"""Unit tests for :class:`BandpassFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.bandpass_filter import BandpassFilter
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            BandpassFilter(
                signal="x",  # type: ignore[arg-type]
                low_hz=1.0,
                high_hz=40.0,
                _config=KnotConfig(id="b"),
            )

    def test_rejects_non_positive_low(self) -> None:
        with self.assertRaisesRegex(ValueError, "low_hz"):
            BandpassFilter(
                signal=SignalFrame(),
                low_hz=0.0,
                high_hz=40.0,
                _config=KnotConfig(id="b"),
            )

    def test_rejects_low_ge_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            BandpassFilter(
                signal=SignalFrame(),
                low_hz=40.0,
                high_hz=10.0,
                _config=KnotConfig(id="b"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_signal_frame(self) -> None:
        with Tapestry() as t:
            BandpassFilter(
                signal=SignalFrame(signal_id="s"),
                low_hz=1.0,
                high_hz=40.0,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        assert isinstance(result.outputs["b"], SignalFrame)
