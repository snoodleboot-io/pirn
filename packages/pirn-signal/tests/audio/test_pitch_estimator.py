"""Unit tests for :class:`PitchEstimator`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.pitch_estimator import PitchEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPitchEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PitchEstimator:
        return PitchEstimator(
            signal=_up(),
            f_min_hz=80.0,
            f_max_hz=400.0,
            _config=KnotConfig(id="pe"),
        )

    async def test_rejects_non_positive_f_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="f_min_hz"):
            await knot.process(_SIGNAL, f_min_hz=0.0, f_max_hz=400.0)

    async def test_rejects_f_max_le_f_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="f_max_hz"):
            await knot.process(_SIGNAL, f_min_hz=400.0, f_max_hz=80.0)

    async def test_rejects_unknown_algorithm(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="algorithm"):
            await knot.process(_SIGNAL, f_min_hz=80.0, f_max_hz=400.0, algorithm="bad")

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, f_min_hz=80.0, f_max_hz=400.0)
        assert isinstance(out, FeaturePayload)
        assert out.frame.feature_names == ("f0_hz",)
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, f_min_hz=80.0, f_max_hz=400.0)
        assert isinstance(out, FeaturePayload)
        assert out.frame.channel_count == 2
        assert out.data.shape[0] == 2
