"""``WelchEstimator`` — power spectral density via Welch's method.

Algorithm:
    1. Receive the input signal payload, segment_length, and overlap.
    2. Validate segment_length (positive integer) and overlap (non-negative integer
       less than segment_length).
    3. Apply ``scipy.signal.welch`` to estimate the PSD.
    4. Return a SpectrumPayload with frequency_bins = segment_length // 2 + 1.

Math:
    Welch PSD:

    $$\\hat{S}_{\\text{Welch}}(f) = \\frac{1}{K} \\sum_{k=0}^{K-1} \\hat{P}_k(f)$$

    where $L$ = segment_length and $O$ = overlap.

References:
    - Welch, P.D. (1967). "The use of fast Fourier transform for the estimation of power spectra."
      IEEE Trans. Audio Electroacoust., 15(2), 70-73.
    - scipy.signal.welch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload


class WelchEstimator(Knot):
    """Estimate PSD via averaged modified periodograms (Welch's method)."""

    def __init__(
        self,
        *,
        signal: Knot,
        segment_length: Knot | int,
        overlap: Knot | int = 0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            segment_length=segment_length,
            overlap=overlap,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        segment_length: int,
        overlap: int = 0,
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the PSD via Welch's averaged modified periodogram method and return a SpectrumPayload.

        Args:
            signal: Signal payload to estimate the power spectral density from.
            segment_length: Length of each overlapping segment (positive integer).
            overlap: Number of samples shared between consecutive segments
                (non-negative integer, must be < segment_length).

        Returns:
            SpectrumPayload with PSD data and ``frequency_bins`` equal to segment_length // 2 + 1.

        Raises:
            ValueError: If segment_length or overlap are invalid.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError("WelchEstimator: segment_length must be a positive integer")
        if not isinstance(overlap, int) or overlap < 0:
            raise ValueError("WelchEstimator: overlap must be a non-negative integer")
        if overlap >= segment_length:
            raise ValueError("WelchEstimator: overlap must be smaller than segment_length")

        freqs, pxx = await asyncio.to_thread(
            ss.welch,
            signal.data,
            fs=signal.frame.sample_rate_hz,
            window="hann",
            nperseg=segment_length,
            noverlap=overlap,
            axis=-1,
        )

        freq_bins = len(freqs)
        freq_res = (
            signal.frame.sample_rate_hz / segment_length if signal.frame.sample_rate_hz > 0 else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=pxx,
        )
