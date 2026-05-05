"""Unit tests for :class:`BeatTracker`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.beat_tracker import BeatTracker
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "hop_length"):
                BeatTracker(
                    signal=sig,
                    hop_length=0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_positive_tempo_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "tempo_min_bpm"):
                BeatTracker(
                    signal=sig,
                    hop_length=512,
                    tempo_min_bpm=0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_tempo_max_le_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "tempo_max_bpm"):
                BeatTracker(
                    signal=sig,
                    hop_length=512,
                    tempo_min_bpm=120.0,
                    tempo_max_bpm=120.0,
                    _config=KnotConfig(id="b"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BeatTracker(
                signal=sig,
                hop_length=512,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert out["feature"] == "beats"
        assert out["hop_length"] == 512
