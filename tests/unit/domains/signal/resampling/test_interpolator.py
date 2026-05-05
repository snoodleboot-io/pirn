"""Unit tests for :class:`Interpolator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.interpolator import Interpolator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_target_sample_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "target_sample_rate_hz"):
                Interpolator(
                    signal=sig,
                    target_sample_rate_hz=0,
                    _config=KnotConfig(id="i"),
                )

    def test_rejects_invalid_kind(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "kind"):
                Interpolator(
                    signal=sig,
                    target_sample_rate_hz=2000.0,
                    kind="bogus",
                    _config=KnotConfig(id="i"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_target_rate(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            Interpolator(
                signal=sig,
                target_sample_rate_hz=2000.0,
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 2000.0
        assert out.samples_per_channel == 2048
