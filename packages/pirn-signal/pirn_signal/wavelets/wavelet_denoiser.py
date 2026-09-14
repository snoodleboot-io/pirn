"""``WaveletDenoiser`` — threshold-based wavelet denoising.

Algorithm:
    1. Receive the input signal frame, wavelet, level, and threshold_mode.
    2. Validate wavelet (non-empty string), level (positive integer), and
       threshold_mode (``soft`` or ``hard``).
    3. Apply the DWT to decompose the signal into level detail subbands.
    4. Estimate each channel's noise standard deviation from its own finest-scale
       detail coefficients using the MAD estimator: sigma_hat = MAD(d1) / 0.6745.
    5. Compute the channel's universal threshold: lambda = sigma_hat * sqrt(2 log N).
    6. Apply the selected thresholding to each detail subband — never to the
       approximation band, which is the signal estimate (VisuShrink):
       - ``soft``: d̂ = sign(d) max(|d| - λ, 0)
       - ``hard``: d̂ = d · 1[|d| > λ]
    7. Reconstruct via IDWT from the untouched approximation and the thresholded
       details, and return the denoised SignalPayload.

Math:
    Universal threshold (Donoho-Johnstone):

    $$\\lambda = \\hat{\\sigma} \\sqrt{2 \\log N}$$

    Soft threshold:

    $$\\delta_\\lambda^{\\text{soft}}(d) = \\text{sign}(d) \\cdot \\max(|d| - \\lambda, 0)$$

    Hard threshold:

    $$\\delta_\\lambda^{\\text{hard}}(d) = d \\cdot \\mathbf{1}[|d| > \\lambda]$$

    Reconstruction from the level-:math:`L` approximation :math:`a_L` and details
    :math:`d_1 .. d_L`:

    $$\\hat{x} = W^{-1}\\left(a_L,\\; \\delta_\\lambda(d_L), \\ldots, \\delta_\\lambda(d_1)\\right)$$

References:
    - Donoho, D.L. & Johnstone, I.M. (1994). "Ideal spatial adaptation by wavelet shrinkage."
      Biometrika, 81(3), 425-455.
    - Donoho, D.L. (1995). "De-noising by soft-thresholding." IEEE Trans. Inf. Theory, 41(3),
      613-627.
    - pywt.threshold (same soft/hard rules; not used because it takes one scalar
      threshold, and each channel needs its own):
      https://pywavelets.readthedocs.io/en/latest/ref/thresholding-functions.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.py_wavelets_binding import PyWaveletsBinding
from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


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
            WaveletDenoiser._run_denoising, signal.data, wavelet, level, threshold_mode
        )
        out_frame = SignalFrame(
            signal_id=f"{signal.metadata.signal_id}:denoised-{threshold_mode}",
            channel_count=signal.metadata.channel_count,
            sample_rate_hz=signal.metadata.sample_rate_hz,
            samples_per_channel=denoised.shape[-1],
        )
        return SignalPayload(metadata=out_frame, data=denoised)

    @staticmethod
    def _run_denoising(
        data: np.ndarray, wavelet: str, level: int, threshold_mode: str
    ) -> NDArray[np.floating[Any]]:
        pywt = PyWaveletsBinding.load()
        approximation, *details = pywt.wavedec(data, wavelet, level=level, axis=-1)
        # One noise estimate per channel, from that channel's finest detail band.
        sigma = np.median(np.abs(details[-1]), axis=-1, keepdims=True) / 0.6745
        sample_count = data.shape[-1]
        threshold = sigma * np.sqrt(2 * np.log(sample_count))
        # Detail bands only: the approximation band is the signal estimate itself.
        shrunk = [WaveletDenoiser._shrink(detail, threshold, threshold_mode) for detail in details]
        return pywt.waverec([approximation, *shrunk], wavelet, axis=-1)

    @staticmethod
    def _shrink(
        detail: NDArray[np.floating[Any]], threshold: NDArray[np.floating[Any]], threshold_mode: str
    ) -> NDArray[np.floating[Any]]:
        """Soft or hard threshold ``detail`` against a per-channel ``threshold``."""
        magnitude = np.abs(detail)
        if threshold_mode == "hard":
            return np.where(magnitude > threshold, detail, 0.0)
        return np.sign(detail) * np.maximum(magnitude - threshold, 0.0)
