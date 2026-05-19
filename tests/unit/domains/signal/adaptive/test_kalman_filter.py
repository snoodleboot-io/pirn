"""Unit tests for :class:`KalmanFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.adaptive.kalman_filter import KalmanFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestKalmanFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> KalmanFilter:
        return KalmanFilter(
            signal=_up(),
            process_noise=0.01,
            measurement_noise=0.1,
            _config=KnotConfig(id="k"),
        )

    async def test_rejects_non_positive_state_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="process_noise"):
            await knot.process(_SIGNAL, process_noise=0, measurement_noise=0.1)

    async def test_rejects_non_positive_observation_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="measurement_noise"):
            await knot.process(_SIGNAL, process_noise=0.01, measurement_noise=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, process_noise=0.01, measurement_noise=0.1)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:kalman"
