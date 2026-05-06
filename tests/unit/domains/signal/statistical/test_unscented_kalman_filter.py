"""Unit tests for :class:`UnscentedKalmanFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.unscented_kalman_filter import (
    UnscentedKalmanFilter,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=0, observation_dim=1)

    async def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=0)

    async def test_rejects_non_positive_alpha(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=1, alpha=0)

    async def test_rejects_non_numeric_beta(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=1, beta="bad")  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            UnscentedKalmanFilter(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="ukf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ukf"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:ukf"
