"""Unit tests for :class:`FIRFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.fir_filter import FIRFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestFIRFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> FIRFilter:
        return FIRFilter(
            signal=_up(),
            coefficients=(0.25, 0.5, 0.25),
            _config=KnotConfig(id="fir"),
        )

    async def test_rejects_empty_coefficients(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="coefficients"):
            await knot.process(_SIGNAL, coefficients=())

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, coefficients=(0.25, 0.5, 0.25))
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:fir"
