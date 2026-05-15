"""``WaveletDenoiser`` — threshold-based wavelet denoising.

Algorithm:
    1. Receive the input signal frame, wavelet, level, and threshold_mode.
    2. Validate wavelet (non-empty string), level (positive integer), and
       threshold_mode (``soft`` or ``hard``).
    3. Apply the DWT to decompose the signal into level detail subbands.
    4. Estimate the noise standard deviation from the finest-scale detail coefficients
       using the MAD estimator: sigma_hat = MAD(d1) / 0.6745.
    5. Compute the universal threshold: lambda = sigma_hat * sqrt(2 log N).
    6. Apply the selected thresholding to each detail subband:
       - ``soft``: d̂ = sign(d) max(|d| - λ, 0)
       - ``hard``: d̂ = d · 1[|d| > λ]
    7. Reconstruct via IDWT and return the denoised SignalFrame.

Math:
    Universal threshold (Donoho-Johnstone):

    $$\\lambda = \\hat{\\sigma} \\sqrt{2 \\log N}$$

    Soft threshold:

    $$\\delta_\\lambda^{\\text{soft}}(d) = \\text{sign}(d) \\cdot \\max(|d| - \\lambda, 0)$$

References:
    - Donoho, D.L. & Johnstone, I.M. (1994). "Ideal spatial adaptation by wavelet shrinkage."
      Biometrika, 81(3), 425-455.
    - pywt.threshold: https://pywavelets.readthedocs.io/en/latest/ref/thresholding-functions.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pywt

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _run_denoising(data: np.ndarray, wavelet: str, level: int, threshold_mode: str) -> np.ndarray:
    coeffs = pywt.wavedec(data, wavelet, level=level, axis=-1)
    finest_detail = coeffs[-1]
    sigma = np.median(np.abs(finest_detail)) / 0.6745
    sample_count = data.shape[-1]
    threshold = sigma * np.sqrt(2 * np.log(sample_count))
    coeffs_thresh = [pywt.threshold(c, threshold, mode=threshold_mode) for c in coeffs]
    return pywt.waverec(coeffs_thresh, wavelet, axis=-1)


class WaveletDenoiser(Knot):
    """Denoise a signal by thresholding wavelet coefficients."""

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet: Knot | str,
        level: Knot | int,
        threshold_mode: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            wavelet=wavelet,
            level=level,
            threshold_mode=threshold_mode,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        wavelet: str,
        level: int,
        threshold_mode: str,
        **_: Any,
    ) -> SignalPayload:
        """Denoise the signal via wavelet thresholding and return the cleaned SignalPayload.

        Args:
            signal: The noisy input signal payload.
            wavelet: Wavelet name (non-empty string).
            level: Decomposition level for DWT (positive integer).
            threshold_mode: Thresholding strategy — ``soft`` or ``hard``.

        Returns:
            Denoised SignalPayload with the same frame metadata and denoised data.

        Raises:
            ValueError: If wavelet, level, or threshold_mode are invalid.
        """
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("WaveletDenoiser: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("WaveletDenoiser: level must be a positive integer")
        if threshold_mode not in {"soft", "hard"}:
            raise ValueError("WaveletDenoiser: threshold_mode must be one of 'soft', 'hard'")
        denoised = await asyncio.to_thread(
            _run_denoising, signal.data, wavelet, level, threshold_mode
        )
        out_frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:denoised-{threshold_mode}",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=denoised.shape[-1],
        )
        return SignalPayload(metadata=out_frame, data=denoised)
