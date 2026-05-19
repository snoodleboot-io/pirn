"""Unit tests for :class:`ParticleFilter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.particle_filter import ParticleFilter
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload, make_signal_payload


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
            await k.process(signal=signal, state_dim=2, particle_count=100, resampling_strategy="bogus")


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
        assert out.frame.signal_id == "test:particle"
