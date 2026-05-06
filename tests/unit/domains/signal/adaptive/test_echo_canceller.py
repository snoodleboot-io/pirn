"""Unit tests for :class:`EchoCanceller`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.adaptive.echo_canceller import EchoCanceller
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_MIC = make_signal_frame(signal_id="test")
_FAR = make_signal_frame(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


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
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
