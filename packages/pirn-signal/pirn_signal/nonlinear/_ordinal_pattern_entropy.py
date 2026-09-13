"""``OrdinalPatternEntropy`` — shared permutation-entropy helper (private, not a Knot).

Factors out the ordinal-pattern-frequency computation duplicated between
:class:`EntropyEstimator` and :class:`PermutationEntropyCalculator`. The two
knots differ only in whether they use a sample delay > 1 and whether they
need the normalised value; both call :meth:`OrdinalPatternEntropy.compute`,
which always returns ``(entropy, normalized_entropy)``.

References:
    [1] Bandt, C. & Pompe, B. (2002). "Permutation entropy: a natural complexity
        measure for time series." Phys. Rev. Lett., 88(17), 174102.
"""

from __future__ import annotations

import math

import numpy as np


class OrdinalPatternEntropy:
    """Permutation entropy shared by ``pirn_signal.nonlinear`` knots."""

    @staticmethod
    def compute(
        signal_array: np.ndarray, pattern_order: int, delay: int = 1
    ) -> tuple[float, float]:
        """Compute permutation entropy and normalised permutation entropy.

        Returns (permutation_entropy, normalized_entropy).
        """
        signal_length = len(signal_array)
        counts: dict[tuple[int, ...], int] = {}
        for start_idx in range(0, signal_length - (pattern_order - 1) * delay, 1):
            sub = signal_array[start_idx : start_idx + pattern_order * delay : delay]
            if len(sub) < pattern_order:
                continue
            pattern = tuple(int(rank) for rank in np.argsort(sub))
            counts[pattern] = counts.get(pattern, 0) + 1
        total = sum(counts.values())
        if total == 0:
            return 0.0, 0.0
        probs = np.array([v / total for v in counts.values()])
        entropy_value = float(-np.sum(probs * np.log(probs + 1e-12)))
        max_h = math.log(math.factorial(pattern_order))
        normalized = entropy_value / max_h if max_h > 0 else 0.0
        return entropy_value, normalized
