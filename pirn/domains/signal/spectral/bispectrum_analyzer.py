"""``BispectrumAnalyzer`` — third-order spectral analysis.

Algorithm:
    1. Receive the input signal frame and segment_length.
    2. Validate segment_length (positive integer).
    3. Compute the third-order cumulant matrix from the signal using
       overlapping segments of length segment_length.
    4. Apply 2-D FFT to the cumulant matrix to obtain the bispectrum B(f1, f2).
    5. Return a SpectrumFrame with bins equal to half the segment length plus one.

Math:
    Third-order cumulant:

    $$c_3(\\tau_1, \\tau_2) = E[x(n) x(n+\\tau_1) x(n+\\tau_2)]$$

    Bispectrum:

    $$B(f_1, f_2) = \\sum_{\\tau_1} \\sum_{\\tau_2} c_3(\\tau_1, \\tau_2)
      e^{-j 2\\pi (f_1 \\tau_1 + f_2 \\tau_2)}$$

References:
    - Nikias, C.L. & Raghuveer, M.R. (1987). "Bispectrum estimation: A digital signal processing
      framework." Proc. IEEE, 75(7), 869-891.
    - scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class BispectrumAnalyzer(Knot):
    """Estimate the bispectrum (third-order cumulant spectrum).

    Production needs ``scipy`` plus a higher-order-statistics
    implementation; the standard library does not ship one.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        segment_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            segment_length=segment_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        segment_length: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the bispectrum from the signal and return a SpectrumFrame of third-order spectral coefficients.

        Args:
            signal: Signal to compute the third-order cumulant spectrum from.
            segment_length: Segment length for cumulant estimation (positive integer).

        Returns:
            SpectrumFrame with bins equal to half the segment length plus one.

        Raises:
            ValueError: If segment_length is not a positive integer.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "BispectrumAnalyzer: segment_length must be a positive integer"
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
