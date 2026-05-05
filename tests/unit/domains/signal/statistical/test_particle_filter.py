"""Unit tests for :class:`ParticleFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.particle_filter import ParticleFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "state_dim"):
                ParticleFilter(
                    signal=sig,
                    state_dim=0,
                    particle_count=100,
                    _config=KnotConfig(id="pf"),
                )

    def test_rejects_non_positive_particle_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "particle_count"):
                ParticleFilter(
                    signal=sig,
                    state_dim=2,
                    particle_count=0,
                    _config=KnotConfig(id="pf"),
                )

    def test_rejects_invalid_resampling_strategy(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "resampling_strategy"):
                ParticleFilter(
                    signal=sig,
                    state_dim=2,
                    particle_count=100,
                    resampling_strategy="bogus",
                    _config=KnotConfig(id="pf"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ParticleFilter(
                signal=sig,
                state_dim=2,
                particle_count=100,
                _config=KnotConfig(id="pf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pf"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:particle"
