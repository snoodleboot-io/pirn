"""Unit tests for :class:`BandpassFilterBank`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.bandpass_filter_bank import BandpassFilterBank
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBandpassFilterBank(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BandpassFilterBank:
        return BandpassFilterBank(
            signal=_up(),
            bands=((100.0, 200.0), (200.0, 400.0)),
            order=4,
            _config=KnotConfig(id="bfb"),
        )

    async def test_rejects_empty_bands(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="bands"):
            await knot.process(_SIGNAL, bands=(), order=4)

    async def test_rejects_non_positive_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="order"):
            await knot.process(_SIGNAL, bands=((100.0, 500.0),), order=0)

    async def test_emits_signal_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, bands=((100.0, 200.0), (200.0, 400.0)), order=4)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:bp-bank"
