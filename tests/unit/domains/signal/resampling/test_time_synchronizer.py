"""Unit tests for :class:`TimeSynchronizer`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.time_synchronizer import TimeSynchronizer
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_REFERENCE = make_signal_frame()
_TARGET = make_signal_frame(signal_id="target")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestTimeSynchronizer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> TimeSynchronizer:
        return TimeSynchronizer(
            reference=_up("reference"),
            target=_up("target"),
            max_lag_samples=128,
            _config=KnotConfig(id="ts"),
        )

    async def test_rejects_non_positive_max_lag_samples(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="max_lag_samples"):
            await knot.process(_REFERENCE, _TARGET, max_lag_samples=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_REFERENCE, _TARGET, max_lag_samples=128)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "target:synced"
