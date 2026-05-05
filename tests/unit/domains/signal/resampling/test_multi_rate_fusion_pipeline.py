"""Unit tests for :class:`MultiRateFusionPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.multi_rate_fusion_pipeline import MultiRateFusionPipeline
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame, emit_signal_b_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_output_rate(self) -> None:
        with Tapestry():
            a = emit_signal_frame(_config=KnotConfig(id="a"))
            b = emit_signal_b_frame(_config=KnotConfig(id="b"))
            with self.assertRaisesRegex(ValueError, "output_rate_hz"):
                MultiRateFusionPipeline(
                    signal_a=a,
                    signal_b=b,
                    output_rate_hz=0.0,
                    _config=KnotConfig(id="mrf"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            a = emit_signal_frame(_config=KnotConfig(id="a"))
            b = emit_signal_b_frame(_config=KnotConfig(id="b"))
            mrf = MultiRateFusionPipeline(
                signal_a=a,
                signal_b=b,
                output_rate_hz=8000.0,
                _config=KnotConfig(id="mrf"),
            )
        assert mrf.output_rate_hz == 8000.0


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_tuple_of_signal_frames(self) -> None:
        with Tapestry() as t:
            a = emit_signal_frame(_config=KnotConfig(id="a"))
            b = emit_signal_b_frame(_config=KnotConfig(id="b"))
            MultiRateFusionPipeline(
                signal_a=a,
                signal_b=b,
                output_rate_hz=2000.0,
                _config=KnotConfig(id="mrf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mrf"]
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert isinstance(out[0], SignalFrame)
        assert isinstance(out[1], SignalFrame)
        assert out[0].sample_rate_hz == 2000.0
        assert out[1].sample_rate_hz == 2000.0
