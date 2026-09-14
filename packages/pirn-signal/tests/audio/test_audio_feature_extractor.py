"""Unit tests for :class:`AudioFeatureExtractor`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.audio_feature_extractor import AudioFeatureExtractor
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestAudioFeatureExtractor(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AudioFeatureExtractor:
        return AudioFeatureExtractor(
            signal=_up(),
            n_mfcc=13,
            n_fft=512,
            hop_length=256,
            _config=KnotConfig(id="fe"),
        )

    async def test_rejects_non_positive_n_mfcc(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_mfcc"):
            await knot.process(_SIGNAL, n_mfcc=0, n_fft=512, hop_length=256)

    async def test_rejects_non_positive_n_fft(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_fft"):
            await knot.process(_SIGNAL, n_mfcc=13, n_fft=0, hop_length=256)

    async def test_rejects_non_positive_hop_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, n_mfcc=13, n_fft=512, hop_length=0)

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, n_mfcc=13, n_fft=512, hop_length=256)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == (
            "rms_energy",
            "zero_crossing_rate",
            "spectral_centroid",
            "spectral_bandwidth",
            "spectral_rolloff",
        )
        assert out.data.shape[0] == 1
        assert out.data.shape[1] == 5

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, n_mfcc=13, n_fft=512, hop_length=256)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2
        assert out.data.shape[1] == 5
