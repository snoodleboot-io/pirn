"""Unit tests for :class:`ChebyshevType1Filter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.chebyshev_type1_filter import ChebyshevType1Filter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestChebyshevType1Filter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ChebyshevType1Filter:
        return ChebyshevType1Filter(
            signal=_up(),
            order=4,
            passband_ripple_db=1.0,
            cutoff_hz=100.0,
            _config=KnotConfig(id="ch1"),
        )

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=0, passband_ripple_db=1.0, cutoff_hz=100.0)

    async def test_rejects_non_positive_ripple(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="passband_ripple_db"):
            await knot.process(_SIGNAL, order=4, passband_ripple_db=0.0, cutoff_hz=100.0)

    async def test_rejects_non_positive_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="cutoff_hz"):
            await knot.process(_SIGNAL, order=4, passband_ripple_db=1.0, cutoff_hz=0.0)

    async def test_emits_signal_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=4, passband_ripple_db=1.0, cutoff_hz=100.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:cheby1"
