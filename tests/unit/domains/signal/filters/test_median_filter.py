"""Unit tests for :class:`MedianFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.median_filter import MedianFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_even_kernel_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive odd"):
                MedianFilter(signal=sig, kernel_size=4, _config=KnotConfig(id="f"))

    def test_rejects_zero_kernel_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive odd"):
                MedianFilter(signal=sig, kernel_size=0, _config=KnotConfig(id="f"))

    def test_accepts_valid_kernel_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MedianFilter(signal=sig, kernel_size=5, _config=KnotConfig(id="f"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MedianFilter(signal=sig, kernel_size=3, _config=KnotConfig(id="f"))
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:median"
        assert out.sample_rate_hz == 1000.0
