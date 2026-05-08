"""Unit tests for :class:`MEGBeamformer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.meg_beamformer import MEGBeamformer
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="bf")
_SIGNAL = SignalPayload(
    frame=SignalFrame(signal_id="meg", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_STEERING = [1.0, 0.5]
_KNOT = MEGBeamformer(signal=_SIGNAL, steering_vector=_STEERING, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="x", steering_vector=_STEERING)  # type: ignore[arg-type]

    async def test_rejects_non_list_steering(self) -> None:
        with self.assertRaisesRegex(TypeError, "steering_vector"):
            await _KNOT.process(signal=_SIGNAL, steering_vector="x")  # type: ignore[arg-type]

    async def test_rejects_mismatched_steering_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "steering_vector"):
            await _KNOT.process(signal=_SIGNAL, steering_vector=[1.0])

    async def test_returns_dict_with_required_keys(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, steering_vector=_STEERING)
        assert isinstance(out, dict)
        assert "beamformed_power" in out
        assert "weight_vector" in out
        assert len(out["weight_vector"]) == 2
