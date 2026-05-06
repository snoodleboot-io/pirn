"""Unit tests for :class:`LowPassFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.low_pass_filter import LowPassFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestLowPassFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> LowPassFilter:
        return LowPassFilter(
            signal=_up(),
            cutoff_hz=500.0,
            _config=KnotConfig(id="lp"),
        )

    async def test_rejects_non_positive_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="cutoff_hz"):
            await knot.process(_SIGNAL, cutoff_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, cutoff_hz=500.0)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:lowpass"
