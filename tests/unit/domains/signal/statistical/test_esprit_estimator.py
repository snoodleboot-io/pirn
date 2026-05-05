"""Unit tests for :class:`ESPRITEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.esprit_estimator import ESPRITEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_subspace_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "signal_subspace_dim"):
                ESPRITEstimator(
                    signal=sig,
                    signal_subspace_dim=0,
                    _config=KnotConfig(id="e"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ESPRITEstimator(
                signal=sig,
                signal_subspace_dim=2,
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert out["estimator"] == "esprit"
        assert out["signal_subspace_dim"] == 2
        assert out["signal_id"] == "test"
