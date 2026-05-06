"""Unit tests for :class:`KalmanSmoother`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.kalman_smoother import KalmanSmoother
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestKalmanSmoother(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> KalmanSmoother:
        return KalmanSmoother(
            signal=_up(),
            state_dim=2,
            observation_dim=1,
            _config=KnotConfig(id="ks"),
        )

    async def test_rejects_non_positive_state_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="state_dim"):
            await knot.process(_SIGNAL, state_dim=0, observation_dim=1)

    async def test_rejects_non_positive_observation_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="observation_dim"):
            await knot.process(_SIGNAL, state_dim=2, observation_dim=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, state_dim=2, observation_dim=1)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:kalman-smooth"
