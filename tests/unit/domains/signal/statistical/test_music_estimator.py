"""Unit tests for :class:`MUSICEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.music_estimator import MUSICEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_subspace_dim(self) -> None:
        with Tapestry():
            k = MUSICEstimator.__new__(MUSICEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, signal_subspace_dim=0, frequency_grid_size=128)

    async def test_rejects_non_positive_grid_size(self) -> None:
        with Tapestry():
            k = MUSICEstimator.__new__(MUSICEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, signal_subspace_dim=2, frequency_grid_size=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MUSICEstimator(
                signal=sig,
                signal_subspace_dim=2,
                frequency_grid_size=128,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert out["estimator"] == "music"
        assert out["frequency_grid_size"] == 128
