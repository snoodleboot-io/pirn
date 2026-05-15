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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _sample_entropy(signal_array: np.ndarray, template_length: int, tolerance: float) -> float:
    """Sample entropy via Chebyshev template matching (self-matches excluded)."""
    signal_length = len(signal_array)

    def _phi(m_val: int) -> int:
        count = 0
        for template_idx in range(signal_length - m_val):
            template = signal_array[template_idx : template_idx + m_val]
            for compare_idx in range(signal_length - m_val):
                if (
                    template_idx != compare_idx
                    and np.max(np.abs(signal_array[compare_idx : compare_idx + m_val] - template))
                    < tolerance
                ):
                    count += 1
        return count

    match_count_longer = _phi(template_length + 1)
    match_count_base = _phi(template_length)
    if match_count_base == 0:
        return 0.0
    return float(-np.log(match_count_longer / match_count_base))


class SampleEntropyCalculator(Knot):
    """Compute sample entropy of a time series signal."""

    def __init__(
        self,
        *,
        signal: Knot,
        template_length: Knot | int,
        tolerance: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            template_length=template_length,
            tolerance=tolerance,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        template_length: int,
        tolerance: float,
        **_: Any,
    ) -> dict[str, float]:
        """Compute sample entropy of the signal using template matching.

        Args:
            signal: Signal payload to analyse.
            template_length: Template length for pattern matching (positive integer).
            tolerance: Tolerance for template matching (positive float).

        Returns:
            Dictionary with keys ``value``, ``embedding_dim``, and ``tolerance``.

        Raises:
            ValueError: If template_length or tolerance are invalid.
        """
        if not isinstance(template_length, int) or template_length <= 0:
            raise ValueError("SampleEntropyCalculator: template_length must be a positive integer")
        if not isinstance(tolerance, (int, float)) or tolerance <= 0.0:
            raise ValueError("SampleEntropyCalculator: tolerance must be a positive float")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        value = await asyncio.to_thread(
            _sample_entropy, signal_array.astype(float), template_length, float(tolerance)
        )
        return {
            "value": value,
            "embedding_dim": template_length,
            "tolerance": float(tolerance),
        }
