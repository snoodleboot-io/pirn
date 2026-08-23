"""Unit tests for :class:`FIRParksMcClellanFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.filters.fir_parks_mcclellan_filter import FIRParksMcClellanFilter
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()

# Real Hz, not normalized frequencies (PIR-832). The knot documents "band edges
# in Hz" and passes fs=sample_rate_hz straight to scipy.signal.remez, so the old
# (0.0, 0.3, 0.4, 1.0) asked for a 0-0.3 Hz passband on a 1 kHz signal. Older
# scipy accepted that and produced a meaningless tap set; newer scipy rejects the
# degenerate grid, which is how the unit mismatch finally surfaced.
_BANDS_HZ = (0.0, 150.0, 200.0, _SIGNAL.frame.sample_rate_hz / 2)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestFIRParksMcClellanFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> FIRParksMcClellanFilter:
        return FIRParksMcClellanFilter(
            signal=_up(),
            num_taps=31,
            bands=_BANDS_HZ,
            desired=(1.0, 0.0),
            _config=KnotConfig(id="pm"),
        )

    async def test_rejects_even_num_taps(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_taps"):
            await knot.process(_SIGNAL, num_taps=32, bands=_BANDS_HZ, desired=(1.0, 0.0))

    async def test_rejects_odd_length_bands(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="bands"):
            await knot.process(_SIGNAL, num_taps=31, bands=_BANDS_HZ[:3], desired=(1.0,))

    async def test_rejects_mismatched_desired(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="desired"):
            await knot.process(_SIGNAL, num_taps=31, bands=_BANDS_HZ, desired=(1.0,))

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_taps=31, bands=_BANDS_HZ, desired=(1.0, 0.0))
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:fir-pm"
