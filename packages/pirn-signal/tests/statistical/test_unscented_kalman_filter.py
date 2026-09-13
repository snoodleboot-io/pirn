"""Unit tests for :class:`UnscentedKalmanFilter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.statistical.unscented_kalman_filter import (
    UnscentedKalmanFilter,
)
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=0, observation_dim=1)

    async def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=0)

    async def test_rejects_non_positive_alpha(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=1, alpha=0)

    async def test_rejects_non_numeric_beta(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, observation_dim=1, beta="bad")  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            UnscentedKalmanFilter(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="ukf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ukf"]
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:ukf"
