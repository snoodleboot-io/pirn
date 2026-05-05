"""Unit tests for :class:`IIRFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.iir_filter import IIRFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_numerator(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "numerator"):
                IIRFilter(
                    signal=sig,
                    numerator=[],
                    denominator=[1.0],
                    _config=KnotConfig(id="iir"),
                )

    def test_rejects_empty_denominator(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "denominator"):
                IIRFilter(
                    signal=sig,
                    numerator=[1.0],
                    denominator=[],
                    _config=KnotConfig(id="iir"),
                )

    def test_rejects_zero_leading_denominator(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-zero"):
                IIRFilter(
                    signal=sig,
                    numerator=[1.0],
                    denominator=[0.0, 1.0],
                    _config=KnotConfig(id="iir"),
                )

    def test_rejects_non_numeric_coefficient(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(TypeError, "real number"):
                IIRFilter(
                    signal=sig,
                    numerator=[1.0, "x"],  # type: ignore[list-item]
                    denominator=[1.0],
                    _config=KnotConfig(id="iir"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            IIRFilter(
                signal=sig,
                numerator=[1.0, 0.5],
                denominator=[1.0, -0.2],
                _config=KnotConfig(id="iir"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["iir"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:iir"
