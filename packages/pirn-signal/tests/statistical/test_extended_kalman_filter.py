"""Unit tests for :class:`ExtendedKalmanFilter`."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.extended_kalman_filter import (
    ExtendedKalmanFilter,
)
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            k = ExtendedKalmanFilter.__new__(ExtendedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ekf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=0)

    async def test_declares_no_observation_dim_input(self) -> None:
        """Each channel is a scalar observation stream: the input is gone."""
        with Tapestry():
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            knot = ExtendedKalmanFilter(
                signal=sig, state_dim=2, _config=KnotConfig(id="ekf-inputs")
            )
        assert knot.input_names == ("signal", "state_dim")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            ExtendedKalmanFilter(
                signal=sig,
                state_dim=2,
                _config=KnotConfig(id="ekf"),
            )
        stub = np.zeros(1024)
        with patch(
            "pirn_signal.statistical.extended_kalman_filter.ExtendedKalmanFilter._ekf",
            return_value=stub,
        ):
            result = await t.run(RunRequest())
        out = result.outputs["ekf"]
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:ekf"

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = ExtendedKalmanFilter.__new__(ExtendedKalmanFilter)
            object.__setattr__(k, "_config", KnotConfig(id="ekf"))
        multichannel = make_signal_payload(channel_count=3, samples_per_channel=256)
        stub = np.zeros(256)
        with patch(
            "pirn_signal.statistical.extended_kalman_filter.ExtendedKalmanFilter._ekf",
            return_value=stub,
        ):
            out = await k.process(signal=multichannel, state_dim=2)
        assert isinstance(out, SignalPayload)
        assert out.metadata.channel_count == 3
        assert out.data.shape == (3, 256)
