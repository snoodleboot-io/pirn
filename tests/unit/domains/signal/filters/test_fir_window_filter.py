"""Unit tests for :class:`FIRWindowFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.fir_window_filter import FIRWindowFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestFIRWindowFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> FIRWindowFilter:
        return FIRWindowFilter(
            signal=_up(),
            num_taps=31,
            cutoff_hz=100.0,
            window="hamming",
            _config=KnotConfig(id="fwf"),
        )

    async def test_rejects_even_num_taps(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_taps"):
            await knot.process(_SIGNAL, num_taps=32, cutoff_hz=100.0, window="hamming")

    async def test_rejects_non_positive_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="cutoff_hz"):
            await knot.process(_SIGNAL, num_taps=31, cutoff_hz=0.0, window="hamming")

    async def test_rejects_unknown_window(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="window"):
            await knot.process(_SIGNAL, num_taps=31, cutoff_hz=100.0, window="bartlett")

    async def test_emits_signal_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_taps=31, cutoff_hz=100.0, window="hamming")
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:fir-window"
