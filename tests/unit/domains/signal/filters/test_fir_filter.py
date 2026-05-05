"""Unit tests for :class:`FIRFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.fir_filter import FIRFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_coefficients(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                FIRFilter(
                    signal=sig,
                    coefficients=[],
                    _config=KnotConfig(id="fir"),
                )

    def test_rejects_non_numeric_coefficient(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(TypeError, "real number"):
                FIRFilter(
                    signal=sig,
                    coefficients=[1.0, "x"],  # type: ignore[list-item]
                    _config=KnotConfig(id="fir"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            FIRFilter(
                signal=sig,
                coefficients=[0.25, 0.5, 0.25],
                _config=KnotConfig(id="fir"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fir"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:fir"
