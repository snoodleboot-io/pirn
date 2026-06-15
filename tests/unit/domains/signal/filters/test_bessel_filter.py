"""Unit tests for :class:`BesselFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.bessel_filter import BesselFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBesselFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BesselFilter:
        return BesselFilter(
            signal=_up(),
            order=4,
            cutoff_hz=100.0,
            _config=KnotConfig(id="bsl"),
        )

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, order=0, cutoff_hz=100.0)

    async def test_rejects_non_positive_cutoff(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="cutoff_hz"):
            await knot.process(_SIGNAL, order=4, cutoff_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, order=4, cutoff_hz=100.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:bessel"
