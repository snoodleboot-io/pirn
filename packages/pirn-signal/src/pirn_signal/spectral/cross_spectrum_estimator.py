"""``CrossSpectrumEstimator`` — cross-spectral density between two signals.

Algorithm:
    1. Receive two signal payloads (signal_a, signal_b) and segment_length.
    2. Validate segment_length (positive integer).
    3. Verify that signal_a and signal_b share the same sample rate.
    4. Apply ``scipy.signal.csd`` to estimate the cross-spectral density.
    5. Return a SpectrumPayload with bins = segment_length // 2 + 1.

Math:
    Cross-spectral density:

    $$\\hat{S}_{xy}(f) = \\frac{1}{K} \\sum_{k=1}^{K}
      \\frac{X_k(f) Y_k^*(f)}{N_s}$$

References:
    - Carter, G.C., Knapp, C.H. & Nuttall, A.H. (1973). "Estimation of the magnitude-squared
      coherence function via overlapped fast Fourier transform processing."
      IEEE Trans. Audio Electroacoust., 21(4), 337-344.
    - scipy.signal.csd: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.csd.html
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


class CrossSpectrumEstimator(Knot):
    """Estimate the cross-spectral density between two signals."""

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
        signal_a: SignalPayload,
        signal_b: SignalPayload,
        segment_length: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the cross-spectral density between two signals and return a SpectrumPayload.

        Args:
            signal_a: First signal payload for the cross-spectral density estimate.
            signal_b: Second signal payload for the cross-spectral density estimate.
            segment_length: Segment length for the averaged CSD estimate (positive integer).

        Returns:
            SpectrumPayload with complex CSD data and bins = segment_length // 2 + 1.

        Raises:
            ValueError: If segment_length is invalid or signals have different sample rates.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError("CrossSpectrumEstimator: segment_length must be a positive integer")
        if signal_a.frame.sample_rate_hz != signal_b.frame.sample_rate_hz:
            raise ValueError(
                "CrossSpectrumEstimator: signal_a and signal_b must share a sample rate"
            )

        freqs, pxy = await asyncio.to_thread(
            ss.csd,
            signal_a.data,
            signal_b.data,
            fs=signal_a.frame.sample_rate_hz,
            nperseg=segment_length,
            axis=-1,
        )

        freq_bins = len(freqs)
        freq_res = (
            signal_a.frame.sample_rate_hz / segment_length
            if signal_a.frame.sample_rate_hz > 0
            else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=f"{signal_a.frame.signal_id}|{signal_b.frame.signal_id}",
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=pxy,
        )
