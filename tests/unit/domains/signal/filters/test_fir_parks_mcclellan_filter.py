"""Unit tests for :class:`FIRParksMcClellanFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.fir_parks_mcclellan_filter import FIRParksMcClellanFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestFIRParksMcClellanFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> FIRParksMcClellanFilter:
        return FIRParksMcClellanFilter(
            signal=_up(),
            num_taps=31,
            bands=(0.0, 0.3, 0.4, 1.0),
            desired=(1.0, 0.0),
            _config=KnotConfig(id="pm"),
        )

    async def test_rejects_even_num_taps(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_taps"):
            await knot.process(_SIGNAL, num_taps=32, bands=(0.0, 0.3, 0.4, 1.0), desired=(1.0, 0.0))

    async def test_rejects_odd_length_bands(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="bands"):
            await knot.process(_SIGNAL, num_taps=31, bands=(0.0, 0.3, 0.4), desired=(1.0,))

    async def test_rejects_mismatched_desired(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="desired"):
            await knot.process(_SIGNAL, num_taps=31, bands=(0.0, 0.3, 0.4, 1.0), desired=(1.0,))

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_taps=31, bands=(0.0, 0.3, 0.4, 1.0), desired=(1.0, 0.0))
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:fir-pm"
