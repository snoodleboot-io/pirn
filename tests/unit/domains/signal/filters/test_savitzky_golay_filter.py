"""Unit tests for :class:`SavitzkyGolayFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.savitzky_golay_filter import SavitzkyGolayFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestSavitzkyGolayFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SavitzkyGolayFilter:
        return SavitzkyGolayFilter(
            signal=_up(),
            window_length=11,
            polynomial_order=3,
            _config=KnotConfig(id="sg"),
        )

    async def test_rejects_even_window_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="window_length"):
            await knot.process(_SIGNAL, window_length=10, polynomial_order=3)

    async def test_rejects_polynomial_order_ge_window_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="polynomial_order"):
            await knot.process(_SIGNAL, window_length=5, polynomial_order=5)

    async def test_rejects_negative_polynomial_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="polynomial_order"):
            await knot.process(_SIGNAL, window_length=5, polynomial_order=-1)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, window_length=11, polynomial_order=3)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:savgol"
