"""Unit tests for :class:`EchoCanceller`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.adaptive.echo_canceller import EchoCanceller
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_MIC = make_signal_payload(signal_id="test")
_FAR = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestEchoCanceller(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> EchoCanceller:
        return EchoCanceller(
            microphone=_up("microphone"),
            far_end=_up("far_end"),
            filter_length=64,
            step_size=0.05,
            _config=KnotConfig(id="ec"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_MIC, _FAR, filter_length=0, step_size=0.05)

    async def test_rejects_zero_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_MIC, _FAR, filter_length=64, step_size=0.0)

    async def test_rejects_step_size_above_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_MIC, _FAR, filter_length=64, step_size=2.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_MIC, _FAR, filter_length=64, step_size=0.05)
        assert isinstance(out, SignalPayload)
        assert out.metadata.sample_rate_hz == 1000.0

    async def test_rejects_mismatched_channel_counts(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(
            signal_id="test", channel_count=2, samples_per_channel=1024
        )
        with pytest.raises(ValueError, match="channel count"):
            await knot.process(multichannel, _FAR, filter_length=64, step_size=0.05)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        mic = make_signal_payload(signal_id="test", channel_count=2, samples_per_channel=128)
        far = make_signal_payload(signal_id="reference", channel_count=2, samples_per_channel=128)
        out = await knot.process(mic, far, filter_length=64, step_size=0.05)
        assert isinstance(out, SignalPayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 128)
