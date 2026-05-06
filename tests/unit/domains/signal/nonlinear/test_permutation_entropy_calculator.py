"""Unit tests for :class:`PermutationEntropyCalculator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.nonlinear.permutation_entropy_calculator import (
    PermutationEntropyCalculator,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestPermutationEntropyCalculator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PermutationEntropyCalculator:
        return PermutationEntropyCalculator(
            signal=_up(),
            order=3,
            delay=1,
            _config=KnotConfig(id="pec"),
        )

    async def test_rejects_order_below_two(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=1, delay=1)

    async def test_rejects_order_above_eight(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=9, delay=1)

    async def test_rejects_non_positive_delay(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="delay"):
            await knot.process(_SIGNAL, order=3, delay=0)

    async def test_emits_dict(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=3, delay=1)
        assert isinstance(out, dict)
        assert "permutation_entropy" in out
