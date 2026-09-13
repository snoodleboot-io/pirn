"""Unit tests for :class:`PermutationEntropyCalculator`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.nonlinear.permutation_entropy_calculator import (
    PermutationEntropyCalculator,
)
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_MULTICHANNEL_SIGNAL = make_signal_payload(channel_count=2, samples_per_channel=256)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPermutationEntropyCalculator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PermutationEntropyCalculator:
        return PermutationEntropyCalculator(
            signal=_up(),
            order=3,
            delay=1,
            _config=KnotConfig(id="pec"),
        )

    async def test_rejects_order_below_two(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=1, delay=1)

    async def test_rejects_order_above_eight(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=9, delay=1)

    async def test_rejects_non_positive_delay(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="delay"):
            await knot.process(_SIGNAL, order=3, delay=0)

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=3, delay=1)
        assert isinstance(out, FeaturePayload)
        assert out.frame.feature_names == ("permutation_entropy",)
        assert out.data.shape == (1, 1)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        out = await knot.process(_MULTICHANNEL_SIGNAL, order=3, delay=1)
        assert isinstance(out, FeaturePayload)
        assert out.frame.channel_count == 2
        assert out.data.shape == (2, 1)
