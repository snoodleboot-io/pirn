"""Unit tests for :class:`PisarenkoEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.pisarenko_estimator import PisarenkoEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_sinusoid_count(self) -> None:
        with Tapestry():
            k = PisarenkoEstimator.__new__(PisarenkoEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, sinusoid_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            PisarenkoEstimator(
                signal=sig,
                sinusoid_count=3,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert "frequencies_hz" in out
        assert out["num_sinusoids"] == 3
