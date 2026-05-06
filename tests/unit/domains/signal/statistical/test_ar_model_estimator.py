"""Unit tests for :class:`ARModelEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.ar_model_estimator import ARModelEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, order=0, method="burg")

    async def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, order=4, method="least_squares")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_dict_with_correct_keys(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ARModelEstimator(
                signal=sig, order=3, method="burg", _config=KnotConfig(id="ar")
            )
        result = await t.run(RunRequest())
        out = result.outputs["ar"]
        assert isinstance(out, dict)
        assert set(out.keys()) == {"coefficients", "order", "method", "variance"}
        assert out["order"] == 3
        assert out["method"] == "burg"
        assert len(out["coefficients"]) == 3
        assert isinstance(out["variance"], float)
