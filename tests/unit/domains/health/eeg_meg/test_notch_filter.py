"""Unit tests for :class:`NotchFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.notch_filter import NotchFilter
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            NotchFilter(
                signal="x",  # type: ignore[arg-type]
                notch_hz=60.0,
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            NotchFilter(
                signal=SignalFrame(),
                notch_hz=0.0,
                _config=KnotConfig(id="n"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_signal_frame(self) -> None:
        with Tapestry() as t:
            NotchFilter(
                signal=SignalFrame(signal_id="s"),
                notch_hz=60.0,
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        assert isinstance(result.outputs["n"], SignalFrame)
