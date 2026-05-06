"""Unit tests for :class:`BandpassFilterBank`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.bandpass_filter_bank import BandpassFilterBank
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestBandpassFilterBank(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BandpassFilterBank:
        return BandpassFilterBank(
            signal=_up(),
            bands=((100.0, 500.0), (500.0, 2000.0)),
            order=4,
            _config=KnotConfig(id="bfb"),
        )

    async def test_rejects_empty_bands(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="bands"):
            await knot.process(_SIGNAL, bands=(), order=4)

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, bands=((100.0, 500.0),), order=0)

    async def test_emits_list_of_signal_frames(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, bands=((100.0, 500.0), (500.0, 2000.0)), order=4)
        assert isinstance(out, list)
        assert len(out) == 2
        assert all(isinstance(sf, SignalFrame) for sf in out)
