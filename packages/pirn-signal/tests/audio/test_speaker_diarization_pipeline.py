"""Unit tests for :class:`SpeakerDiarizationPipeline`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401  # imported only to skip when librosa is absent
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.speaker_diarization_pipeline import SpeakerDiarizationPipeline
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


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

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, min_speakers=1, max_speakers=4, embedding_model="ecapa")
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("speaker_label",)
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(
            multichannel, min_speakers=1, max_speakers=4, embedding_model="ecapa"
        )
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2
