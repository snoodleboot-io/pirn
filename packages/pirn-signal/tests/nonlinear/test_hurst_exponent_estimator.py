"""Unit tests for :class:`HurstExponentEstimator`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.nonlinear.hurst_exponent_estimator import HurstExponentEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_MULTICHANNEL_SIGNAL = make_signal_payload(channel_count=2, samples_per_channel=256)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestHurstExponentEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> HurstExponentEstimator:
        return HurstExponentEstimator(
            signal=_up(),
            method="rs",
            _config=KnotConfig(id="he"),
        )

    async def test_rejects_unknown_method(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="method"):
            await knot.process(_SIGNAL, method="unknown")

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, method="rs")
        assert isinstance(out, FeaturePayload)
        assert out.frame.feature_names == ("hurst_exponent",)
        assert out.data.shape == (1, 1)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        out = await knot.process(_MULTICHANNEL_SIGNAL, method="rs")
        assert isinstance(out, FeaturePayload)
        assert out.frame.channel_count == 2
        assert out.data.shape == (2, 1)
