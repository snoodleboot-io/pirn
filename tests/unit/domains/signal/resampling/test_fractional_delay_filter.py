"""Unit tests for :class:`FractionalDelayFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.fractional_delay_filter import FractionalDelayFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_delay_samples(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "delay_samples"):
                FractionalDelayFilter(
                    signal=sig,
                    delay_samples=-0.5,
                    filter_order=4,
                    _config=KnotConfig(id="fd"),
                )

    def test_rejects_non_positive_filter_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "filter_order"):
                FractionalDelayFilter(
                    signal=sig,
                    delay_samples=0.5,
                    filter_order=0,
                    _config=KnotConfig(id="fd"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            fd = FractionalDelayFilter(
                signal=sig,
                delay_samples=0.5,
                filter_order=4,
                _config=KnotConfig(id="fd"),
            )
        assert fd.delay_samples == 0.5
        assert fd.filter_order == 4


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            FractionalDelayFilter(
                signal=sig,
                delay_samples=0.25,
                filter_order=3,
                _config=KnotConfig(id="fd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fd"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
