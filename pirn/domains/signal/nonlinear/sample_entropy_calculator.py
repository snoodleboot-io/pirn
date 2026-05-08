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


def _sample_entropy(x: np.ndarray, m: int, r: float) -> float:
    """Sample entropy via Chebyshev template matching (self-matches excluded)."""
    n = len(x)

    def _phi(m_val: int) -> int:
        count = 0
        for i in range(n - m_val):
            template = x[i : i + m_val]
            for j in range(n - m_val):
                if i != j and np.max(np.abs(x[j : j + m_val] - template)) < r:
                    count += 1
        return count

    a = _phi(m + 1)
    b = _phi(m)
    if b == 0:
        return 0.0
    return float(-np.log(a / b))


class SampleEntropyCalculator(Knot):
    """Compute sample entropy of a time series signal."""

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
        signal: SignalPayload,
        m: int,
        r: float,
        **_: Any,
    ) -> dict[str, float]:
        """Compute sample entropy of the signal using template matching.

        Args:
            signal: Signal payload to analyse.
            m: Template length for pattern matching (positive integer).
            r: Tolerance for template matching (positive float).

        Returns:
            Dictionary with keys ``value``, ``embedding_dim``, and ``tolerance``.

        Raises:
            ValueError: If m or r are invalid.
        """
        if not isinstance(m, int) or m <= 0:
            raise ValueError("SampleEntropyCalculator: m must be a positive integer")
        if not isinstance(r, (int, float)) or r <= 0.0:
            raise ValueError("SampleEntropyCalculator: r must be a positive float")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        value = await asyncio.to_thread(_sample_entropy, x.astype(float), m, float(r))
        return {
            "value": value,
            "embedding_dim": m,
            "tolerance": float(r),
        }
