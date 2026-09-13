"""Unit tests for :class:`RLSAdaptiveFilter`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.adaptive.rls_adaptive_filter import RLSAdaptiveFilter
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_REF = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestRLSAdaptiveFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> RLSAdaptiveFilter:
        return RLSAdaptiveFilter(
            signal=_up("signal"),
            reference=_up("reference"),
            filter_length=8,
            forgetting_factor=0.99,
            _config=KnotConfig(id="rls"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, _REF, filter_length=0, forgetting_factor=0.99)

    async def test_rejects_forgetting_factor_le_zero(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="forgetting_factor"):
            await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=0.0)

    async def test_rejects_forgetting_factor_gt_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="forgetting_factor"):
            await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=1.5)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=0.99)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:rls"

    async def test_rejects_mismatched_channel_counts(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=1024)
        with pytest.raises(ValueError, match="channel count"):
            await knot.process(multichannel, _REF, filter_length=8, forgetting_factor=0.99)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        sig = make_signal_payload(channel_count=2, samples_per_channel=32)
        ref = make_signal_payload(signal_id="reference", channel_count=2, samples_per_channel=32)
        out = await knot.process(sig, ref, filter_length=8, forgetting_factor=0.99)
        assert isinstance(out, SignalPayload)
        assert out.frame.channel_count == 2
        assert out.data.shape == (2, 32)
