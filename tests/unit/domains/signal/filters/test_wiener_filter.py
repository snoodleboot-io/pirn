"""Unit tests for :class:`WienerFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.wiener_filter import WienerFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestWienerFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> WienerFilter:
        return WienerFilter(
            signal=_up(),
            window_size=5,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_non_positive_window_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="window_size"):
            await knot.process(_SIGNAL, window_size=0)

    async def test_rejects_non_positive_noise_power(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="noise_power"):
            await knot.process(_SIGNAL, window_size=5, noise_power=0.0)

    async def test_emits_signal_frame_without_noise_power(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, window_size=5)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:wiener"

    async def test_emits_signal_frame_with_noise_power(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, window_size=5, noise_power=0.01)
        assert isinstance(out, SignalFrame)
