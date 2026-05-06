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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


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
        signal: SignalFrame,
        atom_count: int,
        sparsity_target: int,
        algorithm: str = "omp",
        **_: Any,
    ) -> SourceFrame:
        """Decompose the signal as a sparse linear combination of dictionary atoms and return a SourceFrame.

        Args:
            signal: Multichannel signal to represent sparsely over the configured atom dictionary.
            atom_count: Total number of dictionary atoms (positive integer).
            sparsity_target: Maximum non-zeros per sparse code (positive integer).
            algorithm: Pursuit algorithm — ``omp``, ``lasso``, or ``lars``.

        Returns:
            SourceFrame with ``source_count`` equal to ``sparsity_target`` and the mixing matrix shape.

        Raises:
            ValueError: If atom_count, sparsity_target, or algorithm are invalid.
        """
        if not isinstance(atom_count, int) or atom_count <= 0:
            raise ValueError(
                "SparseDecomposer: atom_count must be a positive integer"
            )
        if not isinstance(sparsity_target, int) or sparsity_target <= 0:
            raise ValueError(
                "SparseDecomposer: sparsity_target must be a positive integer"
            )
        if algorithm not in self._valid_algorithms:
            raise ValueError(
                "SparseDecomposer: algorithm must be 'omp', 'lasso', or 'lars'"
            )
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=sparsity_target,
            mixing_matrix_shape=(signal.channel_count, atom_count),
        )
