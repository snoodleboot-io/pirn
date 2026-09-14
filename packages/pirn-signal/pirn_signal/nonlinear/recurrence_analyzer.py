# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``RecurrenceAnalyzer`` — recurrence-quantification analysis (RQA).

Algorithm:
    1. Receive the input signal frame, embedding_dim, time_delay, and recurrence_threshold.
    2. Validate embedding_dim and time_delay (positive integers) and
       recurrence_threshold (positive float).
    3. Reconstruct the phase space via Takens delay embedding.
    4. Build the recurrence matrix R(i, j) = Theta(eps - ||x_i - x_j||).
    5. Compute RQA measures: recurrence rate (RR), determinism (DET),
       average diagonal line length (L), laminarity (LAM), trapping time (TT).
    6. Repeat independently for each channel and return a FeaturePayload with
       the RR/DET/LAM measures per channel.

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
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.nonlinear._delay_embedding import DelayEmbedding
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


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
    ) -> FeaturePayload:
        """Run recurrence quantification analysis on the signal.

        Args:
            signal: Signal payload to analyse with recurrence quantification.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).
            recurrence_threshold: Distance threshold ε for recurrence (positive float).

        Returns:
            FeaturePayload with ``rr``, ``det``, and ``lam`` measures per channel.

        Raises:
            ValueError: If embedding_dim, time_delay, or recurrence_threshold are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("RecurrenceAnalyzer: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("RecurrenceAnalyzer: time_delay must be a positive integer")
        if not isinstance(recurrence_threshold, (int, float)) or recurrence_threshold <= 0:
            raise ValueError("RecurrenceAnalyzer: recurrence_threshold must be positive")
        channels = np.atleast_2d(signal.data).astype(float)
        rqa_results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    RecurrenceAnalyzer._compute_rqa,
                    channel,
                    embedding_dim,
                    time_delay,
                    float(recurrence_threshold),
                )
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:rqa",
                channel_count=channels.shape[0],
                feature_names=("rr", "det", "lam"),
            ),
            data=np.asarray(rqa_results).reshape(channels.shape[0], 3),
        )

    @staticmethod
    def _recurrence_matrix(
        signal_array: NDArray[np.float64], embedding_dim: int, tau: int, distance_threshold: float
    ) -> NDArray[np.bool_]:
        """Build binary recurrence matrix using Euclidean distance threshold."""
        embedded = DelayEmbedding.embed(signal_array, embedding_dim, tau)
        n_pts = len(embedded)
        if n_pts == 0:
            return np.zeros((0, 0), dtype=bool)
        recurrence_matrix = np.zeros((n_pts, n_pts), dtype=bool)
        for point_idx in range(n_pts):
            reference_point: NDArray[np.float64] = embedded[point_idx]
            dists: NDArray[np.float64] = np.linalg.norm(embedded - reference_point, axis=1)
            recurrence_matrix[point_idx] = dists < distance_threshold
        return recurrence_matrix

    @staticmethod
    def _diagonal_line_lengths(recurrence_mat: NDArray[np.bool_]) -> NDArray[np.int_]:
        """Extract diagonal line lengths from recurrence matrix (excluding main diagonal)."""
        matrix_size = len(recurrence_mat)
        lengths: list[int] = []
        for offset in range(-(matrix_size - 1), matrix_size):
            if offset == 0:
                continue
            diag = np.diag(recurrence_mat, offset)
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

    @staticmethod
    def _vertical_line_lengths(recurrence_mat: NDArray[np.bool_]) -> NDArray[np.int_]:
        """Extract vertical line lengths from recurrence matrix."""
        matrix_size = len(recurrence_mat)
        lengths: list[int] = []
        for col in range(matrix_size):
            count = 0
            for row in range(matrix_size):
                if recurrence_mat[row, col]:
                    count += 1
                elif count >= 2:
                    lengths.append(count)
                    count = 0
                else:
                    count = 0
            if count >= 2:
                lengths.append(count)
        return np.array(lengths)

    @staticmethod
    def _compute_rqa(
        signal_array: NDArray[np.float64], embedding_dim: int, tau: int, distance_threshold: float
    ) -> tuple[float, float, float]:
        """Compute RQA measures: (RR, DET, LAM)."""
        recurrence_mat = RecurrenceAnalyzer._recurrence_matrix(
            signal_array, embedding_dim, tau, distance_threshold
        )
        n_pts = len(recurrence_mat)
        if n_pts == 0:
            return 0.0, 0.0, 0.0
        total = n_pts * n_pts
        rr = float(np.sum(recurrence_mat)) / total
        diag_lengths = RecurrenceAnalyzer._diagonal_line_lengths(recurrence_mat)
        if len(diag_lengths) > 0:
            recurrent_points = float(np.sum(recurrence_mat))
            det = float(np.sum(diag_lengths)) / recurrent_points if recurrent_points > 0 else 0.0
        else:
            det = 0.0
        vert_lengths = RecurrenceAnalyzer._vertical_line_lengths(recurrence_mat)
        if len(vert_lengths) > 0:
            recurrent_points = float(np.sum(recurrence_mat))
            lam = float(np.sum(vert_lengths)) / recurrent_points if recurrent_points > 0 else 0.0
        else:
            lam = 0.0
        return rr, det, lam
