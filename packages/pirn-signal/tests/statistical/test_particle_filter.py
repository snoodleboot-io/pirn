"""Unit tests for :class:`ParticleFilter`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.particle_filter import ParticleFilter
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            k = ParticleFilter.__new__(ParticleFilter)
            object.__setattr__(k, "_config", KnotConfig(id="pf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=0, particle_count=100)

    async def test_rejects_non_positive_particle_count(self) -> None:
        with Tapestry():
            k = ParticleFilter.__new__(ParticleFilter)
            object.__setattr__(k, "_config", KnotConfig(id="pf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, state_dim=2, particle_count=0)

    async def test_rejects_invalid_resampling_strategy(self) -> None:
        with Tapestry():
            k = ParticleFilter.__new__(ParticleFilter)
            object.__setattr__(k, "_config", KnotConfig(id="pf"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                signal=signal, state_dim=2, particle_count=100, resampling_strategy="bogus"
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            ParticleFilter(
                signal=sig,
                state_dim=2,
                particle_count=100,
                _config=KnotConfig(id="pf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pf"]
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:particle"

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = ParticleFilter.__new__(ParticleFilter)
            object.__setattr__(k, "_config", KnotConfig(id="pf"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=32)
        out = await k.process(signal=multichannel, state_dim=2, particle_count=20)
        assert isinstance(out, SignalPayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 32)


class TestStateDimAndResamplingAreUsed(unittest.IsolatedAsyncioTestCase):
    """``state_dim`` and ``resampling_strategy`` were validated and then ignored."""

    @staticmethod
    def _knot() -> ParticleFilter:
        with Tapestry():
            knot = ParticleFilter.__new__(ParticleFilter)
            object.__setattr__(knot, "_config", KnotConfig(id="pf"))
        return knot

    @staticmethod
    def _noisy_ramp() -> SignalPayload:
        rng = np.random.default_rng(3)
        clean = np.linspace(-1.0, 1.0, 96)
        return make_signal_payload(samples_per_channel=96).derive(
            "noisy", clean + 0.3 * rng.standard_normal(96)
        )

    async def test_state_dim_changes_the_filter(self) -> None:
        payload = self._noisy_ramp()
        knot = self._knot()

        scalar_state = await knot.process(signal=payload, state_dim=1, particle_count=200)
        vector_state = await knot.process(signal=payload, state_dim=4, particle_count=200)

        # A 4-dimensional particle state draws four noise components per step, so the
        # estimates cannot be identical to the scalar-state filter's.
        assert not np.allclose(scalar_state.data, vector_state.data)

    async def test_each_resampling_strategy_is_a_distinct_scheme(self) -> None:
        payload = self._noisy_ramp()
        knot = self._knot()
        outputs = {}
        for strategy in ("multinomial", "stratified", "systematic", "residual"):
            out = await knot.process(
                signal=payload,
                state_dim=2,
                particle_count=64,
                resampling_strategy=strategy,
            )
            outputs[strategy] = np.asarray(out.data, dtype=float)

        names = list(outputs)
        for first in range(len(names)):
            for second in range(first + 1, len(names)):
                assert not np.array_equal(outputs[names[first]], outputs[names[second]]), (
                    names[first],
                    names[second],
                )

    async def test_every_strategy_tracks_the_underlying_signal(self) -> None:
        """All four schemes must estimate the signal, not just differ from each other."""
        rng = np.random.default_rng(5)
        clean = np.sin(np.linspace(0.0, 4.0, 128))
        payload = make_signal_payload(samples_per_channel=128).derive(
            "noisy", clean + 0.2 * rng.standard_normal(128)
        )
        knot = self._knot()

        for strategy in ("multinomial", "stratified", "systematic", "residual"):
            out = await knot.process(
                signal=payload,
                state_dim=1,
                particle_count=400,
                resampling_strategy=strategy,
            )
            estimate = np.asarray(out.data, dtype=float).reshape(-1)
            assert float(np.corrcoef(estimate, clean)[0, 1]) > 0.8, strategy

    async def test_estimates_are_reproducible(self) -> None:
        payload = self._noisy_ramp()
        knot = self._knot()

        first = await knot.process(signal=payload, state_dim=2, particle_count=64)
        second = await knot.process(signal=payload, state_dim=2, particle_count=64)

        np.testing.assert_array_equal(first.data, second.data)
