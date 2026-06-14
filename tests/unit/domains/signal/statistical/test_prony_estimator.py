"""Unit tests for :class:`PronyEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.statistical.prony_estimator import PronyEstimator

from tests.unit.domains.signal.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            k = PronyEstimator.__new__(PronyEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, component_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            PronyEstimator(
                signal=sig,
                component_count=4,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert "poles" in out
        assert out["model_order"] == 4
