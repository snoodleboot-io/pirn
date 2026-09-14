"""``DelayEmbedding`` — shared Takens delay-embedding helper (private, not a Knot).

Factors out the delay-embedding construction duplicated byte-for-byte across
three nonlinear-dynamics knots (:class:`CorrelationDimensionEstimator`,
:class:`LyapunovExponentEstimator`, and :class:`RecurrenceAnalyzer`). Each
knot calls :meth:`DelayEmbedding.embed` from its own ``process()``.

References:
    [1] Takens, F. (1981). "Detecting strange attractors in turbulence."
        Dynamical Systems and Turbulence, Lecture Notes in Mathematics 898, 366-381.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class DelayEmbedding:
    """Takens delay embedding shared by ``pirn_signal.nonlinear`` knots."""

    @staticmethod
    def embed(
        signal_array: NDArray[np.float64], embedding_dim: int, tau: int = 1
    ) -> NDArray[np.float64]:
        """Build a delay embedding matrix of shape (N - (embedding_dim-1)*tau, embedding_dim)."""
        signal_length = len(signal_array)
        length = signal_length - (embedding_dim - 1) * tau
        if length <= 0:
            return np.empty((0, embedding_dim))
        return np.array(
            [
                signal_array[start_idx : start_idx + embedding_dim * tau : tau]
                for start_idx in range(length)
            ]
        )
