"""Unit tests for :class:`ARModelEstimator`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.ar_model_estimator import ARModelEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, order=0, method="burg")

    async def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, order=4, method="least_squares")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            ARModelEstimator(signal=sig, order=3, method="burg", _config=KnotConfig(id="ar"))
        result = await t.run(RunRequest())
        out = result.outputs["ar"]
        assert isinstance(out, FeaturePayload)
        assert out.frame.signal_id == "test:ar-burg"
        assert out.frame.feature_names == (
            "ar_coeff_0",
            "ar_coeff_1",
            "ar_coeff_2",
            "variance",
        )
        assert out.data.shape == (1, 4)

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=64)
        out = await k.process(signal=multichannel, order=3, method="burg")
        assert isinstance(out, FeaturePayload)
        assert out.frame.channel_count == 2
        assert out.data.shape == (2, 4)
