"""Unit tests for :class:`AudioResampler`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.audio_resampler import AudioResampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_target_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "target_sample_rate_hz"):
                AudioResampler(
                    signal=sig,
                    target_sample_rate_hz=0,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_invalid_quality(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "quality"):
                AudioResampler(
                    signal=sig,
                    target_sample_rate_hz=22050.0,
                    quality="bogus",
                    _config=KnotConfig(id="r"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_target_rate(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AudioResampler(
                signal=sig,
                target_sample_rate_hz=2000.0,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 2000.0
        assert out.samples_per_channel == 2048
        assert out.signal_id == "test:resampled"
