"""Unit tests for :class:`BandStopFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.band_stop_filter import BandStopFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_low_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "low_cutoff_hz"):
                BandStopFilter(
                    signal=sig,
                    low_cutoff_hz=0,
                    high_cutoff_hz=10.0,
                    _config=KnotConfig(id="bs"),
                )

    def test_rejects_low_ge_high(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "low_cutoff_hz must be"):
                BandStopFilter(
                    signal=sig,
                    low_cutoff_hz=30.0,
                    high_cutoff_hz=20.0,
                    _config=KnotConfig(id="bs"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BandStopFilter(
                signal=sig,
                low_cutoff_hz=10.0,
                high_cutoff_hz=100.0,
                _config=KnotConfig(id="bs"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["bs"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:bandstop"
