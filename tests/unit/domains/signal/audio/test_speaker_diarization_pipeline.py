"""Unit tests for :class:`SpeakerDiarizationPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.speaker_diarization_pipeline import SpeakerDiarizationPipeline
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_min_speakers_below_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "min_speakers"):
                SpeakerDiarizationPipeline(
                    signal=sig,
                    min_speakers=0,
                    max_speakers=4,
                    embedding_model="ecapa",
                    _config=KnotConfig(id="sd"),
                )

    def test_rejects_empty_embedding_model(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "embedding_model"):
                SpeakerDiarizationPipeline(
                    signal=sig,
                    min_speakers=1,
                    max_speakers=4,
                    embedding_model="",
                    _config=KnotConfig(id="sd"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            sd = SpeakerDiarizationPipeline(
                signal=sig,
                min_speakers=1,
                max_speakers=5,
                embedding_model="ecapa",
                _config=KnotConfig(id="sd"),
            )
        assert sd.min_speakers == 1
        assert sd.max_speakers == 5
        assert sd.embedding_model == "ecapa"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_segment_list(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SpeakerDiarizationPipeline(
                signal=sig,
                min_speakers=1,
                max_speakers=3,
                embedding_model="ecapa",
                _config=KnotConfig(id="sd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sd"]
        assert isinstance(out, list)
        assert len(out) >= 1
        segment = out[0]
        assert "start_sec" in segment
        assert "end_sec" in segment
        assert "speaker_id" in segment
