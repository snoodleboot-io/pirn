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
            await k.process(signal=signal, state_dim=0)

    async def test_declares_no_observation_dim_input(self) -> None:
        """Each channel is a scalar observation stream: the input is gone."""
        with Tapestry():
            sig = emit_signal_payload(_config=KnotConfig(id="sig-inputs"))
            knot = UnscentedKalmanFilter(
                signal=sig, state_dim=2, _config=KnotConfig(id="ukf-inputs")
            )
        assert knot.input_names == ("signal", "state_dim", "alpha", "beta", "kappa")

    async def test_rejects_non_positive_alpha(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, alpha=0)

    async def test_rejects_non_numeric_beta(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, beta="bad")  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            UnscentedKalmanFilter(
                signal=sig,
                state_dim=2,
                _config=KnotConfig(id="ukf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ukf"]
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:ukf"

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = UnscentedKalmanFilter.__new__(UnscentedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ukf"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=32)
        out = await k.process(signal=multichannel, state_dim=2)
        assert isinstance(out, SignalPayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 32)
