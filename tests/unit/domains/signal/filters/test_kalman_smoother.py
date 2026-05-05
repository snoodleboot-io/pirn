"""Unit tests for :class:`KalmanSmoother`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.kalman_smoother import KalmanSmoother
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_state_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "state_dim"):
                KalmanSmoother(
                    signal=sig,
                    state_dim=0,
                    observation_dim=1,
                    _config=KnotConfig(id="ks"),
                )

    def test_rejects_non_positive_observation_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "observation_dim"):
                KalmanSmoother(
                    signal=sig,
                    state_dim=2,
                    observation_dim=0,
                    _config=KnotConfig(id="ks"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            KalmanSmoother(
                signal=sig,
                state_dim=2,
                observation_dim=1,
                _config=KnotConfig(id="ks"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ks"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:kalman-smooth"
