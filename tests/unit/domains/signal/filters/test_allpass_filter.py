"""Unit tests for :class:`AllpassFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.allpass_filter import AllpassFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestAllpassFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AllpassFilter:
        return AllpassFilter(
            signal=_up(),
            pole_radius=0.5,
            _config=KnotConfig(id="ap"),
        )

    async def test_rejects_pole_radius_at_zero(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="pole_radius"):
            await knot.process(_SIGNAL, pole_radius=0.0)

    async def test_rejects_pole_radius_at_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="pole_radius"):
            await knot.process(_SIGNAL, pole_radius=1.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, pole_radius=0.5)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:allpass"
