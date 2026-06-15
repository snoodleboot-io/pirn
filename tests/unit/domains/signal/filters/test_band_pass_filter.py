"""Unit tests for :class:`BandPassFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.band_pass_filter import BandPassFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBandPassFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BandPassFilter:
        return BandPassFilter(
            signal=_up(),
            low_cutoff_hz=200.0,
            high_cutoff_hz=800.0,
            _config=KnotConfig(id="bp"),
        )

    async def test_rejects_non_positive_low_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="low_cutoff_hz"):
            await knot.process(_SIGNAL, low_cutoff_hz=0.0, high_cutoff_hz=800.0)

    async def test_rejects_low_ge_high(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError):
            await knot.process(_SIGNAL, low_cutoff_hz=800.0, high_cutoff_hz=200.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, low_cutoff_hz=200.0, high_cutoff_hz=400.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:bandpass"
