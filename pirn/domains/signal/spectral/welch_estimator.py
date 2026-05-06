"""``WelchEstimator`` — power spectral density via Welch's method.

Algorithm:
    1. Receive the input signal frame, segment_length, and overlap.
    2. Validate segment_length (positive integer) and overlap (non-negative integer
       less than segment_length).
    3. Partition the signal into overlapping segments of segment_length samples
       with an overlap of ``overlap`` samples.
    4. Apply a Hann window to each segment and compute the periodogram.
    5. Average the modified periodograms to obtain the Welch PSD estimate.
    6. Return a SpectrumFrame with frequency_bins equal to half the segment length plus one.

Math:
    Number of segments:

    $$K = 1 + \\left\\lfloor \\frac{N - L}{L - O} \\right\\rfloor$$

    Welch PSD:

    $$\\hat{S}_{\\text{Welch}}(f) = \\frac{1}{K} \\sum_{k=0}^{K-1} \\hat{P}_k(f)$$

    where $L$ = segment_length and $O$ = overlap.

References:
    - Welch, P.D. (1967). "The use of fast Fourier transform for the estimation of power spectra."
      IEEE Trans. Audio Electroacoust., 15(2), 70-73.
    - scipy.signal.welch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class WelchEstimator(Knot):
    """Estimate PSD via averaged modified periodograms (Welch's method).

    Production needs ``scipy.signal.welch``; this stub validates the
    segmentation parameters and emits a :class:`SpectrumFrame` reference.
    """

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
        signal: SignalFrame,
        segment_length: int,
        overlap: int = 0,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the PSD via Welch's averaged modified periodogram method and return a SpectrumFrame.

        Args:
            signal: Signal to estimate the power spectral density from via Welch's method.
            segment_length: Length of each overlapping segment (positive integer).
            overlap: Number of samples shared between consecutive segments
                (non-negative integer, must be < segment_length).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to half the segment length plus one.

        Raises:
            ValueError: If segment_length or overlap are invalid.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "WelchEstimator: segment_length must be a positive integer"
            )
        if not isinstance(overlap, int) or overlap < 0:
            raise ValueError(
                "WelchEstimator: overlap must be a non-negative integer"
            )
        if overlap >= segment_length:
            raise ValueError(
                "WelchEstimator: overlap must be smaller than segment_length"
            )
        resolution = (
            signal.sample_rate_hz / segment_length
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
