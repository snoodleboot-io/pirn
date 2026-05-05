"""Unit tests for :class:`PronyEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.prony_estimator import PronyEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "component_count"):
                PronyEstimator(
                    signal=sig,
                    component_count=0,
                    _config=KnotConfig(id="p"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PronyEstimator(
                signal=sig,
                component_count=4,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert out["estimator"] == "prony"
        assert out["component_count"] == 4
