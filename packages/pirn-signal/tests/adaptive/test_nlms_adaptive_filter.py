"""Unit tests for :class:`NLMSAdaptiveFilter`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.adaptive.nlms_adaptive_filter import NLMSAdaptiveFilter
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_REF = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestNLMSAdaptiveFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> NLMSAdaptiveFilter:
        return NLMSAdaptiveFilter(
            signal=_up("signal"),
            reference=_up("reference"),
            filter_length=8,
            step_size=0.01,
            _config=KnotConfig(id="nlms"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, _REF, filter_length=0, step_size=0.01)

    async def test_rejects_non_positive_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_SIGNAL, _REF, filter_length=8, step_size=0)

    async def test_rejects_negative_regularization(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="regularization"):
            await knot.process(_SIGNAL, _REF, filter_length=8, step_size=0.01, regularization=-1.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, filter_length=8, step_size=0.01)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:nlms"

    async def test_rejects_mismatched_channel_counts(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=1024)
        with pytest.raises(ValueError, match="channel count"):
            await knot.process(multichannel, _REF, filter_length=8, step_size=0.01)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        sig = make_signal_payload(channel_count=2, samples_per_channel=64)
        ref = make_signal_payload(signal_id="reference", channel_count=2, samples_per_channel=64)
        out = await knot.process(sig, ref, filter_length=8, step_size=0.01)
        assert isinstance(out, SignalPayload)
        assert out.frame.channel_count == 2
        assert out.data.shape == (2, 64)
