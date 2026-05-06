"""Unit tests for :class:`MedianFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.median_filter import MedianFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestMedianFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MedianFilter:
        return MedianFilter(
            signal=_up(),
            kernel_size=5,
            _config=KnotConfig(id="med"),
        )

    async def test_rejects_even_kernel_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="kernel_size"):
            await knot.process(_SIGNAL, kernel_size=4)

    async def test_rejects_non_positive_kernel_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="kernel_size"):
            await knot.process(_SIGNAL, kernel_size=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, kernel_size=5)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:median"
