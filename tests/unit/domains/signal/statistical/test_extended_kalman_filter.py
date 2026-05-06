"""Unit tests for :class:`ExtendedKalmanFilter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.extended_kalman_filter import (
    ExtendedKalmanFilter,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            k = ExtendedKalmanFilter.__new__(ExtendedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ekf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=0, observation_dim=1)

    async def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            k = ExtendedKalmanFilter.__new__(ExtendedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ekf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ExtendedKalmanFilter(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="ekf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ekf"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:ekf"
