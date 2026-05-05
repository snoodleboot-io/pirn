"""Unit tests for :class:`VADDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.vad_detector import VADDetector
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_frame_duration(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "frame_duration_ms"):
                VADDetector(
                    signal=sig,
                    frame_duration_ms=15,
                    aggressiveness=1,
                    _config=KnotConfig(id="vad"),
                )

    def test_rejects_aggressiveness_above_three(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "aggressiveness"):
                VADDetector(
                    signal=sig,
                    frame_duration_ms=20,
                    aggressiveness=4,
                    _config=KnotConfig(id="vad"),
                )

    def test_rejects_negative_aggressiveness(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "aggressiveness"):
                VADDetector(
                    signal=sig,
                    frame_duration_ms=20,
                    aggressiveness=-1,
                    _config=KnotConfig(id="vad"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            vad = VADDetector(
                signal=sig,
                frame_duration_ms=30,
                aggressiveness=2,
                _config=KnotConfig(id="vad"),
            )
        assert vad.frame_duration_ms == 30
        assert vad.aggressiveness == 2


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_segment_list(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            VADDetector(
                signal=sig,
                frame_duration_ms=20,
                aggressiveness=1,
                _config=KnotConfig(id="vad"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["vad"]
        assert isinstance(out, list)
        assert len(out) >= 1
        segment = out[0]
        assert "start_sec" in segment
        assert "end_sec" in segment
        assert "is_speech" in segment
