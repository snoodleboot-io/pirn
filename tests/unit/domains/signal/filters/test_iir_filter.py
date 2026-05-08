"""Unit tests for :class:`IIRFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.iir_filter import IIRFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestIIRFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> IIRFilter:
        return IIRFilter(
            signal=_up(),
            numerator=(1.0, 0.5),
            denominator=(1.0, -0.5),
            _config=KnotConfig(id="iir"),
        )

    async def test_rejects_empty_numerator(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="numerator"):
            await knot.process(_SIGNAL, numerator=(), denominator=(1.0,))

    async def test_rejects_empty_denominator(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="denominator"):
            await knot.process(_SIGNAL, numerator=(1.0,), denominator=())

    async def test_rejects_zero_denominator_first(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="denominator"):
            await knot.process(_SIGNAL, numerator=(1.0,), denominator=(0.0, 1.0))

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, numerator=(1.0, 0.5), denominator=(1.0, -0.5))
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:iir"
