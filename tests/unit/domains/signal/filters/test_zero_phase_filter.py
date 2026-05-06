"""Unit tests for :class:`ZeroPhaseFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.zero_phase_filter import ZeroPhaseFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestZeroPhaseFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ZeroPhaseFilter:
        return ZeroPhaseFilter(
            signal=_up(),
            filter_type="lowpass",
            cutoff_hz=1000.0,
            order=4,
            _config=KnotConfig(id="zpf"),
        )

    async def test_rejects_unknown_filter_type(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_type"):
            await knot.process(_SIGNAL, filter_type="notch", cutoff_hz=1000.0, order=4)

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, filter_type="lowpass", cutoff_hz=1000.0, order=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, filter_type="lowpass", cutoff_hz=1000.0, order=4)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:zerophase-lowpass"
