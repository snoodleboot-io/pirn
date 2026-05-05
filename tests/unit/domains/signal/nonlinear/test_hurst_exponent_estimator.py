"""Unit tests for :class:`HurstExponentEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.hurst_exponent_estimator import (
    HurstExponentEstimator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "method"):
                HurstExponentEstimator(
                    signal=sig,
                    method="bogus",
                    _config=KnotConfig(id="h"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            HurstExponentEstimator(
                signal=sig,
                method="rs",
                _config=KnotConfig(id="h"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["h"]
        assert out["estimator"] == "hurst"
        assert out["method"] == "rs"
