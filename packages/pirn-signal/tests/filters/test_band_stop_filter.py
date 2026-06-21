"""Unit tests for :class:`BandStopFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.band_stop_filter import BandStopFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBandStopFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BandStopFilter:
        return BandStopFilter(
            signal=_up(),
            low_cutoff_hz=45.0,
            high_cutoff_hz=55.0,
            _config=KnotConfig(id="bs"),
        )

    async def test_rejects_non_positive_low_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="low_cutoff_hz"):
            await knot.process(_SIGNAL, low_cutoff_hz=0.0, high_cutoff_hz=55.0)

    async def test_rejects_low_ge_high(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError):
            await knot.process(_SIGNAL, low_cutoff_hz=55.0, high_cutoff_hz=45.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, low_cutoff_hz=45.0, high_cutoff_hz=55.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:bandstop"
