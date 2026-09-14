"""Unit tests for :class:`HurstExponentEstimator`."""

from __future__ import annotations

import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.nonlinear.hurst_exponent_estimator import HurstExponentEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload
from tests.reference_signals import ReferenceSignals

_RNG = np.random.default_rng(3)
_SIGNAL = SignalPayload(metadata=make_signal_payload().metadata, data=_RNG.standard_normal(1024))
_MULTICHANNEL_SIGNAL = SignalPayload(
    metadata=make_signal_payload(channel_count=2, samples_per_channel=256).metadata,
    data=_RNG.standard_normal((2, 256)),
)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestHurstExponentEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> HurstExponentEstimator:
        return HurstExponentEstimator(
            signal=_up(),
            method="rs",
            _config=KnotConfig(id="he"),
        )

    async def test_rejects_unknown_method(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="method"):
            await knot.process(_SIGNAL, method="unknown")

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, method="rs")
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("hurst_exponent",)
        assert out.data.shape == (1, 1)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        out = await knot.process(_MULTICHANNEL_SIGNAL, method="rs")
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 1)


class TestHurstExponentReference(unittest.IsolatedAsyncioTestCase):
    """Recover the Hurst exponent of exact fractional Gaussian noise (Davies-Harte).

    fGn of Hurst exponent ``H`` has, by construction, R/S and DFA fluctuation
    scaling ``n^H`` (Hurst 1951; Peng et al. 1994) and orthonormal Haar detail
    variance ``2^{j(2H-1)}`` at octave ``j`` (Abry & Veitch 1998).
    """

    def _make(self) -> HurstExponentEstimator:
        return HurstExponentEstimator(signal=_up(), method="rs", _config=KnotConfig(id="he"))

    @staticmethod
    def _fgn_payload(hurst: float, seed: int) -> SignalPayload:
        samples = ReferenceSignals.fractional_gaussian_noise(hurst, 2**14, seed)
        return SignalPayload(
            metadata=make_signal_payload(samples_per_channel=samples.size).metadata,
            data=samples,
        )

    async def test_wavelet_method_recovers_known_hurst_exponent(self) -> None:
        knot = self._make()
        for hurst in (0.3, 0.5, 0.8):
            out = await knot.process(self._fgn_payload(hurst, seed=11), method="wavelet")
            assert abs(float(out.data[0, 0]) - hurst) < 0.03, (hurst, out.data)

    async def test_dfa_method_recovers_known_hurst_exponent(self) -> None:
        knot = self._make()
        for hurst in (0.3, 0.5, 0.8):
            out = await knot.process(self._fgn_payload(hurst, seed=12), method="dfa")
            assert abs(float(out.data[0, 0]) - hurst) < 0.05, (hurst, out.data)

    async def test_rs_method_recovers_known_hurst_exponent(self) -> None:
        # R/S carries a known small-sample upward bias near H = 0.5 (Anis & Lloyd 1976).
        knot = self._make()
        for hurst in (0.3, 0.5, 0.8):
            out = await knot.process(self._fgn_payload(hurst, seed=13), method="rs")
            assert abs(float(out.data[0, 0]) - hurst) < 0.1, (hurst, out.data)

    async def test_too_short_a_signal_raises_instead_of_reporting_one_half(self) -> None:
        knot = self._make()
        short = SignalPayload(
            metadata=make_signal_payload(samples_per_channel=8).metadata,
            data=np.random.default_rng(0).standard_normal(8),
        )
        for method in ("rs", "dfa", "wavelet"):
            with pytest.raises(ValueError, match="too short"):
                await knot.process(short, method=method)

    async def test_constant_signal_raises_instead_of_reporting_one_half(self) -> None:
        knot = self._make()
        flat = SignalPayload(
            metadata=make_signal_payload(samples_per_channel=4096).metadata,
            data=np.ones(4096),
        )
        for method in ("rs", "dfa", "wavelet"):
            with pytest.raises(ValueError, match="constant"):
                await knot.process(flat, method=method)
