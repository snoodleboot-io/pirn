"""Unit tests for :class:`KalmanSmoother`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.filters.kalman_smoother import KalmanSmoother
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestKalmanSmoother(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> KalmanSmoother:
        return KalmanSmoother(
            signal=_up(),
            state_dim=2,
            _config=KnotConfig(id="ks"),
        )

    async def test_rejects_non_positive_state_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="state_dim"):
            await knot.process(_SIGNAL, state_dim=0)

    def test_declares_no_observation_dim_input(self) -> None:
        """The observation dimension is the signal's channel count, not an input."""
        assert self._make().input_names == ("signal", "state_dim")

    async def test_rejects_a_state_smaller_than_the_channel_count(self) -> None:
        """A 3-channel signal cannot be observed by a 2-dimensional state."""
        knot = self._make()
        multichannel = make_signal_payload(channel_count=3, samples_per_channel=32)
        with pytest.raises(ValueError, match="channel count"):
            await knot.process(multichannel, state_dim=2)

    async def test_smooths_every_channel_of_a_multichannel_signal(self) -> None:
        import numpy as np

        knot = self._make()
        rng = np.random.default_rng(0)
        clean = np.vstack([np.linspace(0.0, 1.0, 64), np.linspace(1.0, 0.0, 64)])
        noisy = clean + 0.2 * rng.standard_normal(clean.shape)
        payload = make_signal_payload(channel_count=2, samples_per_channel=64).derive(
            "noisy", noisy
        )

        out = await knot.process(payload, state_dim=2)

        # The smoother must reduce the noise on both channels, not only the first.
        for channel in range(2):
            before = float(np.mean((noisy[channel] - clean[channel]) ** 2))
            after = float(np.mean((out.data[channel] - clean[channel]) ** 2))
            assert after < before, (channel, after, before)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, state_dim=2)
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:kalman-smooth"
