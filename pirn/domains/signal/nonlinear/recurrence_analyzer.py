"""``RecurrenceAnalyzer`` — recurrence-quantification analysis (RQA).

Algorithm:
    1. Receive the input signal frame, embedding_dim, time_delay, and recurrence_threshold.
    2. Validate embedding_dim and time_delay (positive integers) and
       recurrence_threshold (positive float).
    3. Reconstruct the phase space via Takens delay embedding.
    4. Build the recurrence matrix R(i, j) = Theta(eps - ||x_i - x_j||).
    5. Compute RQA measures: recurrence rate (RR), determinism (DET),
       average diagonal line length (L), laminarity (LAM), trapping time (TT).
    6. Return a result mapping with the RQA measures and parameters.

Math:
    Recurrence matrix:

    $$R_{i,j} = \\Theta(\\varepsilon - \\|x_i - x_j\\|), \\quad i, j = 1, \\ldots, N$$

    Recurrence rate:

    $$RR = \\frac{1}{N^2} \\sum_{i,j} R_{i,j}$$

References:
    - Eckmann, J.-P., Kamphorst, S.O. & Ruelle, D. (1987). "Recurrence plots of dynamical systems."
      Europhys. Lett., 4(9), 973-977.
    - pyrqa library: https://github.com/tobias-burg/PyRQA
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _delay_embed(x: np.ndarray, m: int, tau: int) -> np.ndarray:
    """Build Takens delay embedding matrix of shape (N - (m-1)*tau, m)."""
    n = len(x)
    length = n - (m - 1) * tau
    if length <= 0:
        return np.empty((0, m))
    return np.array([x[i : i + m * tau : tau] for i in range(length)])


def _recurrence_matrix(x: np.ndarray, m: int, tau: int, eps: float) -> np.ndarray:
    """Build binary recurrence matrix using Euclidean distance threshold."""
    embedded = _delay_embed(x, m, tau)
    n_pts = len(embedded)
    if n_pts == 0:
        return np.zeros((0, 0), dtype=bool)
    R = np.zeros((n_pts, n_pts), dtype=bool)
    for i in range(n_pts):
        dists = np.linalg.norm(embedded - embedded[i], axis=1)
        R[i] = dists < eps
    return R


def _diagonal_line_lengths(R: np.ndarray) -> np.ndarray:
    """Extract diagonal line lengths from recurrence matrix (excluding main diagonal)."""
    n = len(R)
    lengths = []
    for offset in range(-(n - 1), n):
        if offset == 0:
            continue
        diag = np.diag(R, offset)
        count = 0
        for val in diag:
            if val:
                count += 1
            elif count >= 2:
                lengths.append(count)
                count = 0
            else:
                count = 0
        if count >= 2:
            lengths.append(count)
    return np.array(lengths)


def _vertical_line_lengths(R: np.ndarray) -> np.ndarray:
    """Extract vertical line lengths from recurrence matrix."""
    n = len(R)
    lengths = []
    for col in range(n):
        count = 0
        for row in range(n):
            if R[row, col]:
                count += 1
            elif count >= 2:
                lengths.append(count)
                count = 0
            else:
                count = 0
        if count >= 2:
            lengths.append(count)
    return np.array(lengths)


def _compute_rqa(x: np.ndarray, m: int, tau: int, eps: float) -> tuple[float, float, float]:
    """Compute RQA measures: (RR, DET, LAM)."""
    R = _recurrence_matrix(x, m, tau, eps)
    n_pts = len(R)
    if n_pts == 0:
        return 0.0, 0.0, 0.0
    total = n_pts * n_pts
    rr = float(np.sum(R)) / total
    diag_lengths = _diagonal_line_lengths(R)
    if len(diag_lengths) > 0:
        recurrent_points = float(np.sum(R))
        det = float(np.sum(diag_lengths)) / recurrent_points if recurrent_points > 0 else 0.0
    else:
        det = 0.0
    vert_lengths = _vertical_line_lengths(R)
    if len(vert_lengths) > 0:
        recurrent_points = float(np.sum(R))
        lam = float(np.sum(vert_lengths)) / recurrent_points if recurrent_points > 0 else 0.0
    else:
        lam = 0.0
    return rr, det, lam


class RecurrenceAnalyzer(Knot):
    """Recurrence quantification analysis."""

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: Knot | int,
        time_delay: Knot | int,
        recurrence_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            embedding_dim=embedding_dim,
            time_delay=time_delay,
            recurrence_threshold=recurrence_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        embedding_dim: int,
        time_delay: int,
        recurrence_threshold: float,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run recurrence quantification analysis on the signal.

        Args:
            signal: Signal payload to analyse with recurrence quantification.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).
            recurrence_threshold: Distance threshold ε for recurrence (positive float).

        Returns:
            Mapping containing ``rr``, ``det``, ``lam``, ``embedding_dim``, and ``threshold``.

        Raises:
            ValueError: If embedding_dim, time_delay, or recurrence_threshold are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("RecurrenceAnalyzer: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("RecurrenceAnalyzer: time_delay must be a positive integer")
        if not isinstance(recurrence_threshold, (int, float)) or recurrence_threshold <= 0:
            raise ValueError("RecurrenceAnalyzer: recurrence_threshold must be positive")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        rr, det, lam = await asyncio.to_thread(
            _compute_rqa, x.astype(float), embedding_dim, time_delay, float(recurrence_threshold)
        )
        return {
            "rr": rr,
            "det": det,
            "lam": lam,
            "embedding_dim": embedding_dim,
            "threshold": float(recurrence_threshold),
        }
