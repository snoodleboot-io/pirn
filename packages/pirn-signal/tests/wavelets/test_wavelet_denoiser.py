"""Unit tests for :class:`WaveletDenoiser`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401  # imported only to skip when scipy is absent
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

try:
    import pywt  # noqa: F401  # imported only to skip when pywt is absent
except ImportError as _e:
    raise unittest.SkipTest("pywt not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.wavelets.wavelet_denoiser import WaveletDenoiser
from tests.conftest import emit_signal_payload, make_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> WaveletDenoiser:
        with Tapestry():
            k = WaveletDenoiser.__new__(WaveletDenoiser)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="", level=3, threshold_mode="soft")

    async def test_rejects_non_positive_level(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="db4", level=0, threshold_mode="soft")

    async def test_rejects_invalid_threshold_mode(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="db4", level=3, threshold_mode="garrote")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_payload_with_mode_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            WaveletDenoiser(
                signal=sig,
                wavelet="db4",
                level=3,
                threshold_mode="soft",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:denoised-soft"
        assert out.metadata.sample_rate_hz == 1000.0


class TestWaveletDenoiserReference(unittest.IsolatedAsyncioTestCase):
    """VisuShrink thresholds detail coefficients only (Donoho & Johnstone 1994).

    The approximation band carries the signal's low-pass content and is never
    shrunk. For the orthonormal Haar wavelet the signal mean is carried entirely by
    the approximation coefficients (details sum to zero), so denoising must leave
    the mean of a dyadic-length signal exactly unchanged.
    """

    @staticmethod
    def _bare() -> WaveletDenoiser:
        with Tapestry():
            k = WaveletDenoiser.__new__(WaveletDenoiser)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    @staticmethod
    def _payload(data: np.ndarray) -> SignalPayload:
        channel_count = 1 if data.ndim == 1 else data.shape[0]
        return SignalPayload(
            metadata=make_signal_payload(
                channel_count=channel_count, samples_per_channel=data.shape[-1]
            ).metadata,
            data=data,
        )

    async def test_approximation_band_is_not_thresholded(self) -> None:
        # Arrange: a small DC offset in unit-variance noise. The universal threshold
        # (~4.3 sigma at N = 4096) far exceeds the approximation coefficients, so
        # shrinking that band would wipe the offset out.
        rng = np.random.default_rng(21)
        samples = 0.1 + rng.standard_normal(4096)

        # Act
        out = await self._bare().process(
            signal=self._payload(samples), wavelet="haar", level=1, threshold_mode="soft"
        )

        # Assert
        assert abs(float(np.mean(out.data)) - float(np.mean(samples))) < 1e-12

    async def test_each_channel_estimates_its_own_noise_level(self) -> None:
        # Arrange: a loud and a quiet channel. Donoho-Johnstone's MAD noise estimate is
        # per signal, so a channel's result must not depend on its neighbours.
        rng = np.random.default_rng(22)
        t = np.arange(2048) / 2048.0
        quiet = np.sin(2 * np.pi * 5 * t) + 0.01 * rng.standard_normal(2048)
        loud = np.sin(2 * np.pi * 5 * t) + 1.0 * rng.standard_normal(2048)
        knot = self._bare()

        # Act
        together = await knot.process(
            signal=self._payload(np.stack([loud, quiet])),
            wavelet="db4",
            level=4,
            threshold_mode="soft",
        )
        alone = await knot.process(
            signal=self._payload(quiet), wavelet="db4", level=4, threshold_mode="soft"
        )

        # Assert
        np.testing.assert_allclose(together.data[1], alone.data, atol=1e-12)
