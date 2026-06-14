"""Unit tests for :class:`TimeSynchronizer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.resampling.time_synchronizer import TimeSynchronizer
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_REFERENCE = make_signal_payload()
_TARGET = make_signal_payload(signal_id="target")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


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
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "target:synced"
