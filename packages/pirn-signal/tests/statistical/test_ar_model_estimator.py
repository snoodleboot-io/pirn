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
from tests.reference_signals import ReferenceSignals


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


class TestARModelReference(unittest.IsolatedAsyncioTestCase):
    """Recover the coefficients of an AR process whose coefficients are known.

    Burg (1975), Yule-Walker (Levinson-Durbin) and ordinary least squares are
    asymptotically equivalent estimators of the same AR(p) model (Kay 1988, ch. 7;
    Box, Jenkins & Reinsel 2015, sec. 7.1), so on a long realisation all three must
    agree with the generating coefficients and with each other, in the one sign
    convention ``x(n) = sum_k phi_k x(n-k) + e(n)``.
    """

    _phi: tuple[float, ...] = (0.75, -0.5, 0.2, -0.1)
    _sigma: float = 0.7

    @staticmethod
    def _bare() -> ARModelEstimator:
        with Tapestry():
            k = ARModelEstimator.__new__(ARModelEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="ar"))
        return k

    def _payload(self) -> SignalPayload:
        samples = ReferenceSignals.autoregressive(self._phi, 20000, seed=5, sigma=self._sigma)
        return SignalPayload(
            metadata=make_signal_payload(samples_per_channel=samples.size).metadata,
            data=samples,
        )

    async def test_every_method_recovers_the_generating_coefficients(self) -> None:
        knot = self._bare()
        payload = self._payload()
        for method in ("burg", "yule_walker", "ols"):
            out = await knot.process(signal=payload, order=len(self._phi), method=method)
            np.testing.assert_allclose(out.data[0, :-1], self._phi, atol=0.03, err_msg=method)
            assert abs(float(out.data[0, -1]) - self._sigma**2) < 0.03, (method, out.data)

    async def test_burg_matches_yule_walker_in_sign_and_value(self) -> None:
        knot = self._bare()
        payload = self._payload()
        burg = await knot.process(signal=payload, order=len(self._phi), method="burg")
        yule_walker = await knot.process(signal=payload, order=len(self._phi), method="yule_walker")
        np.testing.assert_allclose(burg.data, yule_walker.data, atol=0.01)
