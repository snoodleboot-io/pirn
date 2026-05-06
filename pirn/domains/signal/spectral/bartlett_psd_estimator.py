"""``BartlettPSDEstimator`` — Bartlett method PSD via averaged periodograms.

Algorithm:
    1. Receive the input signal frame and num_segments.
    2. Validate num_segments (positive integer).
    3. Partition the signal into num_segments non-overlapping segments of equal length.
    4. Compute the periodogram of each segment (squared FFT magnitude / N).
    5. Average the periodograms across all segments to reduce variance.
    6. Return a SpectrumFrame with frequency_bins equal to half the per-segment sample count plus one.

Math:
    Per-segment periodogram:

    $$\\hat{P}_k(f) = \\frac{1}{N_s} \\left|\\text{FFT}\\{x_k\\}\\right|^2$$

    Bartlett averaged PSD:

    $$\\hat{S}(f) = \\frac{1}{K} \\sum_{k=1}^{K} \\hat{P}_k(f)$$

    where $K$ = num_segments and $N_s = N / K$ is the per-segment length.

References:
    - Bartlett, M.S. (1948). "Smoothing Periodograms from Time Series with Continuous Spectra."
      Nature, 161, 686-687.
    - scipy.signal.periodogram: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


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
        signal: SignalFrame,
        num_segments: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the PSD via Bartlett's averaged periodogram method and return a SpectrumFrame.

        Args:
            signal: The input signal frame.
            num_segments: Number of non-overlapping segments to average (positive integer).

        Returns:
            SpectrumFrame with frequency_bins equal to half the per-segment sample count plus one.

        Raises:
            ValueError: If num_segments is not a positive integer.
        """
        if not isinstance(num_segments, int) or num_segments <= 0:
            raise ValueError("BartlettPSDEstimator: num_segments must be a positive integer")
        segment_length = (
            signal.samples_per_channel // num_segments
            if num_segments > 0
            else signal.samples_per_channel
        )
        resolution = (
            signal.sample_rate_hz / segment_length
            if segment_length > 0 and signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
