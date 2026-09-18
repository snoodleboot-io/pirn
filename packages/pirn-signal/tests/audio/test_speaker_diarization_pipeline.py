"""Unit tests for :class:`SpeakerDiarizationPipeline`."""

from __future__ import annotations

import unittest

try:
    import librosa
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.speaker_diarization_pipeline import SpeakerDiarizationPipeline
from pirn_signal.bindings.sklearn_cluster_binding import SklearnClusterBinding
from pirn_signal.bindings.sklearn_metrics_binding import SklearnMetricsBinding
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
            _config=KnotConfig(id="diar"),
        )

    async def test_rejects_min_speakers_below_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="min_speakers"):
            await knot.process(_SIGNAL, min_speakers=0, max_speakers=4)

    async def test_rejects_max_speakers_below_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="max_speakers"):
            await knot.process(_SIGNAL, min_speakers=3, max_speakers=1)

    def test_declares_no_embedding_model_input(self) -> None:
        """No embedding model is loaded: the pipeline clusters MFCC frames."""
        assert self._make().input_names == ("signal", "min_speakers", "max_speakers")

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, min_speakers=1, max_speakers=4)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("speaker_label",)
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, min_speakers=1, max_speakers=4)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2


class TestSpeakerCountSelection(unittest.IsolatedAsyncioTestCase):
    """The speaker count is chosen inside [min_speakers, max_speakers], not fixed at the top."""

    @staticmethod
    def _two_speaker_signal() -> SignalPayload:
        """Two acoustically distinct halves: a low buzz then a high buzz."""
        sample_rate_hz = 8000.0
        half = np.arange(8192) / sample_rate_hz
        low = np.sin(2 * np.pi * 120.0 * half) + 0.3 * np.sin(2 * np.pi * 240.0 * half)
        high = np.sin(2 * np.pi * 1600.0 * half) + 0.3 * np.sin(2 * np.pi * 3200.0 * half)
        data = np.concatenate([low, high])
        return make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=data.size
        ).derive("two-speakers", data)

    def _knot(self) -> SpeakerDiarizationPipeline:
        return SpeakerDiarizationPipeline(
            signal=_up(),
            min_speakers=1,
            max_speakers=8,
            _config=KnotConfig(id="diar"),
        )

    async def test_the_chosen_clustering_beats_the_max_speakers_clustering(self) -> None:
        """Clustering at max_speakers unconditionally gave a worse-separated labelling."""
        # Arrange
        payload = self._two_speaker_signal()
        max_speakers = 8
        features = librosa.feature.mfcc(
            y=np.asarray(payload.data, dtype=np.float64),
            sr=int(payload.metadata.sample_rate_hz),
            n_mfcc=20,
            hop_length=512,
        ).T
        at_max = SklearnClusterBinding.load().kmeans_labels(features, max_speakers)
        metrics = SklearnMetricsBinding.load()

        # Act
        out = await self._knot().process(payload, min_speakers=1, max_speakers=max_speakers)

        # Assert: fewer speakers than the ceiling, and a better silhouette than it.
        labels = np.asarray(out.data[0], dtype=np.int_)
        assert len(np.unique(labels)) < max_speakers
        assert metrics.silhouette(features, labels) > metrics.silhouette(features, at_max)

    async def test_min_speakers_forces_at_least_that_many_clusters(self) -> None:
        payload = self._two_speaker_signal()

        out = await self._knot().process(payload, min_speakers=4, max_speakers=6)

        assert len(np.unique(out.data[0])) >= 4
