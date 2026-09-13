"""``SampleEntropy`` — shared sample-entropy helper (private, not a Knot).

Factors out the SampEn template-matching computation duplicated byte-for-byte
between :class:`EntropyEstimator` and :class:`SampleEntropyCalculator`. Each
knot calls :meth:`SampleEntropy.compute` from its own ``process()``.

References:
    [1] Richman, J.S. & Moorman, J.R. (2000). "Physiological time-series analysis
        using approximate entropy and sample entropy." Am. J. Physiol., 278(6),
        H2039-H2049.
"""

from __future__ import annotations

import numpy as np


class SampleEntropy:
    """Sample entropy (SampEn) shared by ``pirn_signal.nonlinear`` knots."""

    @staticmethod
    def compute(signal_array: np.ndarray, template_length: int, tolerance: float) -> float:
        """Sample entropy via Chebyshev template matching (self-matches excluded)."""
        match_count_longer = SampleEntropy._match_count(
            signal_array, template_length + 1, tolerance
        )
        match_count_base = SampleEntropy._match_count(signal_array, template_length, tolerance)
        if match_count_base == 0:
            return 0.0
        return float(-np.log(match_count_longer / match_count_base))

    @staticmethod
    def _match_count(signal_array: np.ndarray, m_val: int, tolerance: float) -> int:
        """Count template matches of length ``m_val`` (excluding self-matches)."""
        signal_length = len(signal_array)
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
