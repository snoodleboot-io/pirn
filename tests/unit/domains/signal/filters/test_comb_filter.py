"""Unit tests for :class:`CombFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.comb_filter import CombFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestCombFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> CombFilter:
        return CombFilter(
            signal=_up(),
            delay_samples=100,
            gain=0.5,
            _config=KnotConfig(id="comb"),
        )

    async def test_rejects_non_positive_delay_samples(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="delay_samples"):
            await knot.process(_SIGNAL, delay_samples=0, gain=0.5)

    async def test_rejects_gain_above_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="gain"):
            await knot.process(_SIGNAL, delay_samples=100, gain=1.5)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, delay_samples=100, gain=0.5)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:comb"
