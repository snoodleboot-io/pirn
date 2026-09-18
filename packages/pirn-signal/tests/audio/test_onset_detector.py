"""Unit tests for :class:`OnsetDetector`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401  # imported only to skip when librosa is absent
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.onset_detector import OnsetDetector
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestOnsetDetector(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> OnsetDetector:
        return OnsetDetector(
            signal=_up(),
            hop_length=512,
            _config=KnotConfig(id="od"),
        )

    async def test_rejects_non_positive_hop_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, hop_length=0)

    async def test_rejects_non_positive_threshold(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="threshold"):
            await knot.process(_SIGNAL, hop_length=512, threshold=0.0)

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, hop_length=512, threshold=0.5)
        assert isinstance(out, FeaturePayload)
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, hop_length=512, threshold=0.5)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2
