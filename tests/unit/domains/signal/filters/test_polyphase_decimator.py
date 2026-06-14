"""Unit tests for :class:`PolyphaseDecimator`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.polyphase_decimator import PolyphaseDecimator
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPolyphaseDecimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PolyphaseDecimator:
        return PolyphaseDecimator(
            signal=_up(),
            decimation_factor=4,
            filter_taps=64,
            _config=KnotConfig(id="pd"),
        )

    async def test_rejects_decimation_factor_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="decimation_factor"):
            await knot.process(_SIGNAL, decimation_factor=1, filter_taps=64)

    async def test_rejects_non_positive_filter_taps(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_taps"):
            await knot.process(_SIGNAL, decimation_factor=4, filter_taps=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, decimation_factor=4, filter_taps=64)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:polyphase-dec"
