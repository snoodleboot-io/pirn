"""Unit tests for :class:`ButterworthFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.butterworth_filter import ButterworthFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestButterworthFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ButterworthFilter:
        return ButterworthFilter(
            signal=_up(),
            order=4,
            cutoff_hz=1000.0,
            _config=KnotConfig(id="bw"),
        )

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=0, cutoff_hz=1000.0)

    async def test_rejects_unknown_band_type(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="band_type"):
            await knot.process(_SIGNAL, order=4, cutoff_hz=1000.0, band_type="notch")

    async def test_emits_signal_payload_lowpass(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=4, cutoff_hz=100.0, band_type="lowpass")
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:butter-lowpass"
