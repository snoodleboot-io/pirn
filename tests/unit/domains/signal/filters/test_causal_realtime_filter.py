"""Unit tests for :class:`CausalRealtimeFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.causal_realtime_filter import CausalRealtimeFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestCausalRealtimeFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> CausalRealtimeFilter:
        return CausalRealtimeFilter(
            signal=_up(),
            filter_type="lowpass",
            cutoff_hz=100.0,
            order=4,
            _config=KnotConfig(id="crf"),
        )

    async def test_rejects_unknown_filter_type(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_type"):
            await knot.process(_SIGNAL, filter_type="notch", cutoff_hz=100.0, order=4)

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, filter_type="lowpass", cutoff_hz=100.0, order=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, filter_type="lowpass", cutoff_hz=100.0, order=4)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:causal-lowpass"
