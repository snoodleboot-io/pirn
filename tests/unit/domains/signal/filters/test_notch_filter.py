"""Unit tests for :class:`NotchFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.notch_filter import NotchFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_notch_hz(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "notch_hz"):
                NotchFilter(
                    signal=sig,
                    notch_hz=0,
                    quality_factor=30.0,
                    _config=KnotConfig(id="n"),
                )

    def test_rejects_non_positive_quality_factor(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "quality_factor"):
                NotchFilter(
                    signal=sig,
                    notch_hz=60.0,
                    quality_factor=0,
                    _config=KnotConfig(id="n"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            NotchFilter(
                signal=sig,
                notch_hz=60.0,
                quality_factor=30.0,
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:notch"
