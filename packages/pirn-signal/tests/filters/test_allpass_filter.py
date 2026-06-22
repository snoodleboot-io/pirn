"""Unit tests for :class:`AllpassFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.allpass_filter import AllpassFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestAllpassFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AllpassFilter:
        return AllpassFilter(
            signal=_up(),
            pole_radius=0.5,
            _config=KnotConfig(id="ap"),
        )

    async def test_rejects_pole_radius_at_zero(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="pole_radius"):
            await knot.process(_SIGNAL, pole_radius=0.0)

    async def test_rejects_pole_radius_at_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="pole_radius"):
            await knot.process(_SIGNAL, pole_radius=1.0)

    async def test_emits_signal_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, pole_radius=0.5)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:allpass"
