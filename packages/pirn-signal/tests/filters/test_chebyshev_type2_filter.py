"""Unit tests for :class:`ChebyshevType2Filter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.chebyshev_type2_filter import ChebyshevType2Filter
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestChebyshevType2Filter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ChebyshevType2Filter:
        return ChebyshevType2Filter(
            signal=_up(),
            order=4,
            stopband_attenuation_db=40.0,
            cutoff_hz=100.0,
            _config=KnotConfig(id="ch2"),
        )

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=0, stopband_attenuation_db=40.0, cutoff_hz=100.0)

    async def test_rejects_non_positive_attenuation(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="stopband_attenuation_db"):
            await knot.process(_SIGNAL, order=4, stopband_attenuation_db=0.0, cutoff_hz=100.0)

    async def test_rejects_non_positive_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="cutoff_hz"):
            await knot.process(_SIGNAL, order=4, stopband_attenuation_db=40.0, cutoff_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=4, stopband_attenuation_db=40.0, cutoff_hz=100.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:cheby2"
