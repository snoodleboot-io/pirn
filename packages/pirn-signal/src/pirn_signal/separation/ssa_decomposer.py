"""``SSADecomposer`` — singular spectrum analysis.

Algorithm:
    1. Receive the input signal frame, embedding_dim, and component_count.
    2. Validate embedding_dim (integer > 1), component_count (positive integer,
       must not exceed embedding_dim).
    3. Embed the signal into a trajectory matrix of shape (embedding_dim x K)
       where K = N - embedding_dim + 1.
    4. Compute the SVD of the trajectory matrix; retain the top component_count
       singular triplets.
    5. Reconstruct each component via diagonal averaging (anti-diagonal means).
    6. Return a SourceFrame with the reconstructed SSA components.

Math:
    Trajectory matrix:

    $$\\mathbf{X} = [X_1, X_2, \\ldots, X_K], \\quad X_i = [x_i, x_{i+1}, \\ldots, x_{i+L-1}]^T$$

    SVD decomposition:

    $$\\mathbf{X} = \\sum_{k=1}^{d} \\sigma_k U_k V_k^T$$

References:
    - Golyandina, N., Nekrutkin, V. & Zhigljavsky, A. (2001). "Analysis of Time Series Structure:
      SSA and Related Techniques." CRC Press.
    - pyts SSA: https://pyts.readthedocs.io/en/stable/generated/pyts.decomposition.SingularSpectrumAnalysis.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


def _ssa(signal_array: np.ndarray, window_length: int, source_count: int) -> np.ndarray:
    signal_length = len(signal_array)
    column_count = signal_length - window_length + 1
    trajectory = np.array(
        [signal_array[col_idx : col_idx + window_length] for col_idx in range(column_count)]
    ).T
    sv_u, sv_s, sv_vt = np.linalg.svd(trajectory, full_matrices=False)
    count = min(source_count, len(sv_s))
    components = np.zeros((count, signal_length))
    for component_idx in range(count):
        rank1 = sv_s[component_idx] * np.outer(sv_u[:, component_idx], sv_vt[component_idx])
        reconstructed = np.zeros(signal_length)
        antidiag_counts = np.zeros(signal_length)
        for col in range(column_count):
            for row in range(window_length):
                reconstructed[row + col] += rank1[row, col]
                antidiag_counts[row + col] += 1
        components[component_idx] = reconstructed / antidiag_counts
    return components


def _run_ssa(data: np.ndarray, window_length: int, source_count: int) -> np.ndarray:
    if data.ndim == 1:
        return _ssa(data, window_length, source_count)
    channel_components = [
        _ssa(data[ch], window_length, source_count) for ch in range(data.shape[0])
    ]
    return np.concatenate(channel_components, axis=0)


class SSADecomposer(Knot):
    """Singular spectrum analysis (trajectory-matrix SVD decomposition).

    Production needs an SSA library (``pyts``, ``hctsa-py``) or a
    hand-rolled SVD implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: Knot | int,
        component_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            embedding_dim=embedding_dim,
            component_count=component_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        embedding_dim: int,
        component_count: int,
        **_: Any,
    ) -> SourcePayload:
        """Decompose the signal via trajectory-matrix SVD and return a SourcePayload of SSA components.

        Args:
            signal: Time series signal to decompose using singular spectrum analysis.
            embedding_dim: Trajectory matrix window length (integer > 1).
            component_count: Number of SSA components to reconstruct (positive integer,
                must not exceed embedding_dim).

        Returns:
            SourcePayload with ``source_count`` equal to ``component_count`` per channel and the
            embedding-matrix shape.

        Raises:
            ValueError: If embedding_dim or component_count are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 1:
            raise ValueError("SSADecomposer: embedding_dim must be an integer > 1")
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError("SSADecomposer: component_count must be a positive integer")
        if component_count > embedding_dim:
            raise ValueError("SSADecomposer: component_count must not exceed embedding_dim")
        components = await asyncio.to_thread(_run_ssa, signal.data, embedding_dim, component_count)
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.frame.signal_id}:ssa",
                source_count=component_count,
                mixing_matrix_shape=(embedding_dim, component_count),
            ),
            data=np.asarray(components),
        )
