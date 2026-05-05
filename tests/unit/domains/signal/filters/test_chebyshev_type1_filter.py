"""Unit tests for :class:`ChebyshevType1Filter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.chebyshev_type1_filter import ChebyshevType1Filter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive integer"):
                ChebyshevType1Filter(
                    signal=sig,
                    order=0,
                    passband_ripple_db=1.0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_non_positive_ripple(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "passband_ripple_db"):
                ChebyshevType1Filter(
                    signal=sig,
                    order=4,
                    passband_ripple_db=0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_non_positive_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "cutoff_hz"):
                ChebyshevType1Filter(
                    signal=sig,
                    order=4,
                    passband_ripple_db=1.0,
                    cutoff_hz=0,
                    _config=KnotConfig(id="c"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ChebyshevType1Filter(
                signal=sig,
                order=4,
                passband_ripple_db=1.0,
                cutoff_hz=50.0,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:cheby1"
