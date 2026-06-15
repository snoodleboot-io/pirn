"""``BartlettPSDEstimator`` — Bartlett method PSD via averaged periodograms.

Algorithm:
    1. Receive the input signal payload and num_segments.
    2. Validate num_segments (positive integer).
    3. Derive segment_length = samples_per_channel // num_segments.
    4. Apply ``scipy.signal.welch`` with boxcar window and no overlap (Bartlett method).
    5. Return a SpectrumPayload with PSD data.

Math:
    Bartlett averaged PSD:

    $$\\hat{S}(f) = \\frac{1}{K} \\sum_{k=1}^{K} \\hat{P}_k(f)$$

    where $K$ = num_segments and $N_s$ is the per-segment length.

References:
    - Bartlett, M.S. (1948). "Smoothing Periodograms from Time Series with Continuous Spectra."
      Nature, 161, 686-687.
    - scipy.signal.welch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


class BartlettPSDEstimator(Knot):
    """Estimate PSD via Bartlett's method: average non-overlapping periodograms."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_segments: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_segments=num_segments,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        num_segments: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the PSD via Bartlett's averaged periodogram method and return a SpectrumPayload.

        Args:
            signal: The input signal payload.
            num_segments: Number of non-overlapping segments to average (positive integer).

        Returns:
            SpectrumPayload with PSD data and frequency_bins = segment_length // 2 + 1.

        Raises:
            ValueError: If num_segments is not a positive integer.
        """
        if not isinstance(num_segments, int) or num_segments <= 0:
            raise ValueError("BartlettPSDEstimator: num_segments must be a positive integer")

        n_samples = signal.data.shape[-1]
        segment_length = n_samples // num_segments if num_segments > 0 else n_samples
        if segment_length <= 0:
            segment_length = 1

        freqs, pxx = await asyncio.to_thread(
            ss.welch,
            signal.data,
            fs=signal.frame.sample_rate_hz,
            window="boxcar",
            nperseg=segment_length,
            noverlap=0,
            axis=-1,
        )

        freq_bins = len(freqs)
        freq_res = (
            signal.frame.sample_rate_hz / segment_length
            if segment_length > 0 and signal.frame.sample_rate_hz > 0
            else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=pxx,
        )
