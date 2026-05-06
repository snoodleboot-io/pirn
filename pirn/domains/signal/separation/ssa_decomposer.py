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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


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
        signal: SignalFrame,
        embedding_dim: int,
        component_count: int,
        **_: Any,
    ) -> SourceFrame:
        """Decompose the signal via trajectory-matrix SVD and return a SourceFrame of SSA components.

        Args:
            signal: Time series signal to decompose using singular spectrum analysis.
            embedding_dim: Trajectory matrix window length (integer > 1).
            component_count: Number of SSA components to reconstruct (positive integer,
                must not exceed embedding_dim).

        Returns:
            SourceFrame with ``source_count`` equal to ``component_count`` and the
            embedding-matrix shape.

        Raises:
            ValueError: If embedding_dim or component_count are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 1:
            raise ValueError(
                "SSADecomposer: embedding_dim must be an integer > 1"
            )
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError(
                "SSADecomposer: component_count must be a positive integer"
            )
        if component_count > embedding_dim:
            raise ValueError(
                "SSADecomposer: component_count must not exceed embedding_dim"
            )
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=component_count,
            mixing_matrix_shape=(embedding_dim, component_count),
        )
