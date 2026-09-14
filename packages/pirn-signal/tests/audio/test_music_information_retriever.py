"""Unit tests for :class:`MusicInformationRetriever`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.music_information_retriever import MusicInformationRetriever
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestMusicInformationRetriever(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MusicInformationRetriever:
        return MusicInformationRetriever(
            signal=_up(),
            feature_set=("chroma", "tempo"),
            _config=KnotConfig(id="mir"),
        )

    async def test_rejects_empty_feature_set(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="feature_set"):
            await knot.process(_SIGNAL, feature_set=())

    async def test_rejects_unknown_feature(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError):
            await knot.process(_SIGNAL, feature_set=("unknown",))

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, feature_set=("chroma", "tempo"))
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("chroma", "tempo")
        assert out.data.shape == (1, 2)
        assert isinstance(out.data[0, 0], np.ndarray)
        assert isinstance(out.data[0, 1], float)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, feature_set=("chroma", "tempo"))
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 2)
