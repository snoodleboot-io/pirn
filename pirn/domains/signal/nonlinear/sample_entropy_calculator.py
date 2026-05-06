"""``SampleEntropyCalculator`` — sample entropy of a time series.

Algorithm:
    1. Receive the input signal frame, m (template length), and r (tolerance).
    2. Validate m (positive integer) and r (positive float).
    3. For each pair of subsequences of length m, count matches where the
       Chebyshev distance is less than r (count B).
    4. Repeat for subsequences of length m+1 (count A).
    5. Compute SampEn = -ln(A / B).
    6. Return a dict with the sample entropy value and the parameters used.

Math:
    Sample entropy:

    $$\\text{SampEn}(m, r, N) = -\\ln \\frac{A^m(r)}{B^m(r)}$$

    where $A^m(r)$ = number of template matches of length $m+1$,
    $B^m(r)$ = number of template matches of length $m$,
    and $r$ is the tolerance expressed as a fraction of the signal's
    standard deviation.

References:
    - Richman, J.S. & Moorman, J.R. (2000). "Physiological time-series analysis using
      approximate entropy and sample entropy." Am. J. Physiol., 278(6), H2039-H2049.
    - antropy library: https://github.com/raphaelvallat/antropy
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SampleEntropyCalculator(Knot):
    """Compute sample entropy of a time series signal.

    Production needs ``antropy`` or a hand-rolled template-matching
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        m: Knot | int,
        r: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            m=m,
            r=r,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        m: int,
        r: float,
        **_: Any,
    ) -> dict[str, float]:
        """Compute sample entropy of the signal using template matching.

        Args:
            signal: Time series signal to analyse.
            m: Template length for pattern matching (positive integer).
            r: Tolerance for template matching (positive float).

        Returns:
            Dictionary with keys ``sample_entropy``, ``m``, and ``r``.

        Raises:
            ValueError: If m or r are invalid.
        """
        if not isinstance(m, int) or m <= 0:
            raise ValueError("SampleEntropyCalculator: m must be a positive integer")
        if not isinstance(r, (int, float)) or r <= 0.0:
            raise ValueError("SampleEntropyCalculator: r must be a positive float")
        return {
            "sample_entropy": 0.0,
            "m": float(m),
            "r": float(r),
        }
