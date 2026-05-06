"""``CrossSpectrumEstimator`` — cross-spectral density between two signals.

Algorithm:
    1. Receive two signal frames (signal_a, signal_b) and segment_length.
    2. Validate segment_length (positive integer).
    3. Verify that signal_a and signal_b share the same sample rate.
    4. Partition both signals into overlapping segments of segment_length.
    5. Compute the cross-periodogram for each segment pair:
       P_ab(f) = FFT{x_a} · conj(FFT{x_b}) / segment_length.
    6. Average the cross-periodograms to obtain the CSD estimate.
    7. Return a SpectrumFrame with bins equal to half the segment length plus one.

Math:
    Cross-spectral density:

    $$\\hat{S}_{xy}(f) = \\frac{1}{K} \\sum_{k=1}^{K}
      \\frac{X_k(f) Y_k^*(f)}{N_s}$$

    where $K$ = number of segments, $N_s$ = segment_length.

References:
    - Carter, G.C., Knapp, C.H. & Nuttall, A.H. (1973). "Estimation of the magnitude-squared
      coherence function via overlapped fast Fourier transform processing." IEEE Trans. Audio
      Electroacoust., 21(4), 337-344.
    - scipy.signal.csd: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.csd.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class CrossSpectrumEstimator(Knot):
    """Estimate the cross-spectral density between two signals.

    Production needs ``scipy.signal.csd``.
    """

    def __init__(
        self,
        *,
        signal_a: Knot,
        signal_b: Knot,
        segment_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal_a=signal_a,
            signal_b=signal_b,
            segment_length=segment_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal_a: SignalFrame,
        signal_b: SignalFrame,
        segment_length: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the cross-spectral density between two signals and return a SpectrumFrame.

        Args:
            signal_a: First signal for the cross-spectral density estimate.
            signal_b: Second signal for the cross-spectral density estimate.
            segment_length: Segment length for the averaged CSD estimate (positive integer).

        Returns:
            SpectrumFrame with bins equal to half the segment length plus one.

        Raises:
            ValueError: If segment_length is invalid or signals have different sample rates.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "CrossSpectrumEstimator: segment_length must be a positive integer"
            )
        if signal_a.sample_rate_hz != signal_b.sample_rate_hz:
            raise ValueError(
                "CrossSpectrumEstimator: signal_a and signal_b must share a sample rate"
            )
        resolution = (
            signal_a.sample_rate_hz / segment_length
            if signal_a.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=f"{signal_a.signal_id}|{signal_b.signal_id}",
            frequency_bins=segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
