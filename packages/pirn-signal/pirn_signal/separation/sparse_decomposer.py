"""``SparseDecomposer`` — sparse decomposition over a fixed dictionary.

Algorithm:
    1. Receive the input signal frame, atom_count, sparsity_target, and algorithm.
    2. Validate atom_count and sparsity_target (positive integers) and algorithm
       (one of ``omp``, ``lasso``, ``lars``).
    3. Initialize a dictionary with atom_count atoms.
    4. Apply the selected pursuit algorithm to find at most sparsity_target
       non-zero coefficients representing each signal column.
    5. Return a SourcePayload with the sparse codes.

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
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.sklearn_decomposition_binding import SklearnDecompositionBinding
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


class SparseDecomposer(Knot):
    """Decompose a signal as a sparse linear combination of learned dictionary atoms."""

    _valid_algorithms: ClassVar[frozenset[str]] = frozenset({"omp", "lasso", "lars"})
    #: Pursuit name -> scikit-learn ``transform_algorithm``.
    _pursuits: ClassVar[dict[str, str]] = {"omp": "omp", "lars": "lars", "lasso": "lasso_cd"}
    #: Dictionary-learning iteration cap.
    _max_iterations: ClassVar[int] = 200

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
            sparsity_target: Maximum non-zeros per sparse code (positive integer).
            algorithm: Pursuit that codes each sample over the learned dictionary —
                ``omp`` and ``lars`` honour ``sparsity_target`` as a hard cap on the
                number of non-zeros per code, ``lasso`` (coordinate descent) instead
                penalises the L1 norm with ``1 / sparsity_target``.

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
        components = await asyncio.to_thread(
            SparseDecomposer._decompose, signal.data, atom_count, sparsity_target, algorithm
        )
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.metadata.signal_id}:sparse",
                source_count=atom_count,
                mixing_matrix_shape=(signal.metadata.channel_count, atom_count),
            ),
            data=components,
        )

    @staticmethod
    def _decompose(
        data: NDArray[np.floating[Any]],
        atom_count: int,
        sparsity_target: int,
        algorithm: str,
    ) -> NDArray[np.float64]:
        """Learn a dictionary and code every time sample with the requested pursuit.

        ``sparsity_target`` is a cap on the non-zeros per code for the greedy pursuits
        (``omp``, ``lars``); ``lasso`` has no such cap, so it reaches scikit-learn as
        the L1 penalty ``1 / sparsity_target`` — a larger target is a weaker penalty.

        Args:
            data: Signal samples shaped ``(channels, samples)``.
            atom_count: Number of dictionary atoms.
            sparsity_target: Maximum non-zeros per code.
            algorithm: ``omp``, ``lars`` or ``lasso``.

        Returns:
            The sparse codes shaped ``(atom_count, samples)``.
        """
        decomposition = SklearnDecompositionBinding.load()
        pursuit = SparseDecomposer._pursuits[algorithm]
        return decomposition.pursuit_codes(
            data.T,
            atom_count,
            alpha=1.0 / float(sparsity_target),
            max_iterations=SparseDecomposer._max_iterations,
            transform_algorithm=pursuit,
            transform_nonzero_coefficients=None if pursuit == "lasso_cd" else sparsity_target,
        ).T
