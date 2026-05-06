"""Unit tests for :class:`NotchFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.notch_filter import NotchFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestNotchFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> NotchFilter:
        return NotchFilter(
            signal=_up(),
            notch_hz=50.0,
            quality_factor=30.0,
            _config=KnotConfig(id="notch"),
        )

    async def test_rejects_non_positive_notch_hz(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="notch_hz"):
            await knot.process(_SIGNAL, notch_hz=0.0, quality_factor=30.0)

    async def test_rejects_non_positive_quality_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="quality_factor"):
            await knot.process(_SIGNAL, notch_hz=50.0, quality_factor=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, notch_hz=50.0, quality_factor=30.0)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:notch"
