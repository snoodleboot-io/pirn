"""Unit tests for :class:`FractionalDelayFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.fractional_delay_filter import FractionalDelayFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestFractionalDelayFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> FractionalDelayFilter:
        return FractionalDelayFilter(
            signal=_up(),
            delay_samples=0.5,
            filter_order=4,
            _config=KnotConfig(id="fdf"),
        )

    async def test_rejects_negative_delay_samples(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="delay_samples"):
            await knot.process(_SIGNAL, delay_samples=-0.5, filter_order=4)

    async def test_rejects_non_positive_filter_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_order"):
            await knot.process(_SIGNAL, delay_samples=0.5, filter_order=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, delay_samples=0.5, filter_order=4)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:frac_delayed"
