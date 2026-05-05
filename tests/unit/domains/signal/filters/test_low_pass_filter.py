"""Unit tests for :class:`LowPassFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.low_pass_filter import LowPassFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "cutoff_hz"):
                LowPassFilter(
                    signal=sig,
                    cutoff_hz=0,
                    _config=KnotConfig(id="lp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            LowPassFilter(
                signal=sig,
                cutoff_hz=100.0,
                _config=KnotConfig(id="lp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lp"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:lowpass"
