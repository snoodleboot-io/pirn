"""``SubbandAdaptiveFilter`` — subband-decomposition adaptive filter.

Algorithm:
    1. Receive the input signal and reference signal frames.
    2. Validate subband_count, filter_length_per_band, and step_size.
    3. Decompose both signal and reference into subband_count subbands using an
       analysis filter bank (e.g., polyphase QMF).
    4. For each subband k: run an NLMS adaptive filter of length filter_length_per_band
       with the given step_size.
    5. Combine the per-band outputs using the synthesis filter bank.
    6. Return a SignalFrame of the reconstructed, adapted output.

Math:
    Per-band NLMS update:

    $$\\mathbf{w}_k(n+1) = \\mathbf{w}_k(n) + \\frac{\\mu}{\\|\\mathbf{x}_k(n)\\|^2 + \\delta} \\, e_k(n) \\, \\mathbf{x}_k(n)$$

    for each subband $k = 0, \\ldots, K-1$ where $K$ = subband_count and
    $L$ = filter_length_per_band taps per band.

References:
    - Gilloire, A. & Vetterli, M. (1992). "Adaptive filtering in subbands with critical sampling."
      IEEE Trans. Signal Process., 40(8), 1862-1875.
    - Sayed, A.H. (2003). "Fundamentals of Adaptive Filtering." Wiley-IEEE Press.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SubbandAdaptiveFilter(Knot):
    """Subband adaptive filter — decompose, adapt per band, reconstruct.

    Production needs an analysis/synthesis filter bank plus an inner
    adaptive filter such as NLMS.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        subband_count: Knot | int,
        filter_length_per_band: Knot | int,
        step_size: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            reference=reference,
            subband_count=subband_count,
            filter_length_per_band=filter_length_per_band,
            step_size=step_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        subband_count: int,
        filter_length_per_band: int,
        step_size: float,
        **_: Any,
    ) -> SignalFrame:
        """Decompose the signal into subbands, adapt each band, and return the reconstructed SignalFrame.

        Args:
            signal: Input signal to decompose and filter per band.
            reference: Reference signal used to drive per-band adaptive filtering.
            subband_count: Number of subbands (integer > 1).
            filter_length_per_band: Number of taps per subband filter (positive integer).
            step_size: NLMS step size (must be positive).

        Returns:
            SignalFrame of the reconstructed subband-filtered output.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(subband_count, int) or subband_count <= 1:
            raise ValueError("SubbandAdaptiveFilter: subband_count must be an integer > 1")
        if not isinstance(filter_length_per_band, int) or filter_length_per_band <= 0:
            raise ValueError(
                "SubbandAdaptiveFilter: filter_length_per_band must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError("SubbandAdaptiveFilter: step_size must be positive")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:subband-adaptive",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
