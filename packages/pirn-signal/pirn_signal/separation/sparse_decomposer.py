"""``SparseDecomposer`` — sparse decomposition over a fixed dictionary.

Algorithm:
    1. Receive the input signal frame, atom_count, sparsity_target, and algorithm.
    2. Validate atom_count and sparsity_target (positive integers) and algorithm
       (one of ``omp``, ``lasso``, ``lars``).
    3. Initialize a dictionary with atom_count atoms.
    4. Apply the selected pursuit algorithm to find at most sparsity_target
       non-zero coefficients representing each signal column.
    5. Return a SourceFrame with the sparse codes.

Math:
    Sparse coding problem (OMP formulation):

    $$\\min_{x} \\|x\\|_0 \\quad \\text{s.t.} \\quad \\|y - Dx\\|_2 \\leq \\varepsilon$$

    LASSO formulation:

    $$\\min_{x} \\frac{1}{2}\\|y - Dx\\|_2^2 + \\lambda \\|x\\|_1$$

References:
    - Mallat, S.G. & Zhang, Z. (1993). "Matching pursuits with time-frequency dictionaries."
      IEEE Trans. Signal Process., 41(12), 3397-3415.
    - sklearn.linear_model: https://scikit-learn.org/stable/modules/linear_model.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from sklearn.decomposition import SparsePCA

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


def _run_sparse_pca(data: np.ndarray, atom_count: int, alpha: float) -> np.ndarray:
    sparse_pca = SparsePCA(n_components=atom_count, alpha=alpha, random_state=0)  # type: ignore[call-overload]
    return sparse_pca.fit_transform(data.T).T


class SparseDecomposer(Knot):
    """Decompose signal as a sparse linear combination of atoms.

    Production needs an OMP / Lasso solver (``sklearn.linear_model``).
    """

    _valid_algorithms = frozenset({"omp", "lasso", "lars"})

    def __init__(
        self,
        *,
        signal: Knot,
        atom_count: Knot | int,
        sparsity_target: Knot | int,
        algorithm: Knot | str = "omp",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            atom_count=atom_count,
            sparsity_target=sparsity_target,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        atom_count: int,
        sparsity_target: int,
        algorithm: str = "omp",
        **_: Any,
    ) -> SourcePayload:
        """Decompose the signal as a sparse linear combination of dictionary atoms and return a SourcePayload.

        Args:
            signal: Multichannel signal to represent sparsely over the configured atom dictionary.
            atom_count: Total number of dictionary atoms / sparse components (positive integer).
            sparsity_target: Maximum non-zeros per sparse code, used as L1 regularisation alpha
                (positive integer).
            algorithm: Pursuit algorithm — ``omp``, ``lasso``, or ``lars`` (retained for API
                compatibility; SparsePCA uses coordinate descent internally).

        Returns:
            SourcePayload with ``source_count`` equal to ``atom_count`` and the mixing matrix shape.

        Raises:
            ValueError: If atom_count, sparsity_target, or algorithm are invalid.
        """
        if not isinstance(atom_count, int) or atom_count <= 0:
            raise ValueError("SparseDecomposer: atom_count must be a positive integer")
        if not isinstance(sparsity_target, int) or sparsity_target <= 0:
            raise ValueError("SparseDecomposer: sparsity_target must be a positive integer")
        if algorithm not in self._valid_algorithms:
            raise ValueError("SparseDecomposer: algorithm must be 'omp', 'lasso', or 'lars'")
        alpha = float(sparsity_target)
        components = await asyncio.to_thread(_run_sparse_pca, signal.data, atom_count, alpha)
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.frame.signal_id}:sparse",
                source_count=atom_count,
                mixing_matrix_shape=(signal.frame.channel_count, atom_count),
            ),
            data=np.asarray(components),
        )
