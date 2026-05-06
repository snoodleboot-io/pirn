"""Unit tests for :class:`SpeakerDiarizationPipeline`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.speaker_diarization_pipeline import SpeakerDiarizationPipeline
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestSpeakerDiarizationPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SpeakerDiarizationPipeline:
        return SpeakerDiarizationPipeline(
            signal=_up(),
            min_speakers=1,
            max_speakers=4,
            embedding_model="ecapa",
            _config=KnotConfig(id="diar"),
        )

    async def test_rejects_min_speakers_below_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="min_speakers"):
            await knot.process(_SIGNAL, min_speakers=0, max_speakers=4, embedding_model="ecapa")

    async def test_rejects_max_speakers_below_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="max_speakers"):
            await knot.process(_SIGNAL, min_speakers=3, max_speakers=1, embedding_model="ecapa")

    async def test_rejects_empty_embedding_model(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_model"):
            await knot.process(_SIGNAL, min_speakers=1, max_speakers=4, embedding_model="")

    async def test_emits_segment_list(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, min_speakers=1, max_speakers=4, embedding_model="ecapa")
        assert isinstance(out, list)
        assert len(out) > 0
        assert "speaker_id" in out[0]
