"""Unit tests for :class:`Interpolator`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.interpolator import Interpolator
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestInterpolator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> Interpolator:
        return Interpolator(
            signal=_up(),
            target_sample_rate_hz=2000.0,
            _config=KnotConfig(id="interp"),
        )

    async def test_rejects_non_positive_target_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="target_sample_rate_hz"):
            await knot.process(_SIGNAL, target_sample_rate_hz=0.0)

    async def test_rejects_invalid_kind(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="kind"):
            await knot.process(_SIGNAL, target_sample_rate_hz=2000.0, kind="bogus")

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, target_sample_rate_hz=2000.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:interp"
        assert out.frame.sample_rate_hz == 2000.0
