"""Unit tests for :class:`ARModelEstimator`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.ar_model_estimator import ARModelEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
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
        assert out.metadata.signal_id == "test:ar-burg"
        assert out.metadata.feature_names == (
            "ar_coeff_0",
            "ar_coeff_1",
            "ar_coeff_2",
            "variance",
        )
        assert out.data.shape == (1, 4)

    async def test_yule_walker_recovers_ar1_coefficient(self) -> None:
        # Arrange: an AR(1) process x[n] = 0.8 x[n-1] + e[n] with a fixed seed.
        rng = np.random.default_rng(7)
        samples = np.zeros(4096)
        for idx in range(1, samples.size):
            samples[idx] = 0.8 * samples[idx - 1] + rng.standard_normal()
        payload = SignalPayload(
            metadata=make_signal_payload(samples_per_channel=samples.size).metadata,
            data=samples,
        )
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))

        # Act
        out = await k.process(signal=payload, order=1, method="yule_walker")

        # Assert: the recovered coefficient matches the generating process and the
        # ordinary-least-squares fit on the same data.
        assert isinstance(out, FeaturePayload)
        assert out.metadata.signal_id == "test:ar-yule_walker"
        assert out.data.shape == (1, 2)
        assert abs(out.data[0, 0] - 0.8) < 0.05
        ols = await k.process(signal=payload, order=1, method="ols")
        assert abs(out.data[0, 0] - ols.data[0, 0]) < 0.02
        assert out.data[0, 1] > 0.0

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=64)
        out = await k.process(signal=multichannel, order=3, method="burg")
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 4)
