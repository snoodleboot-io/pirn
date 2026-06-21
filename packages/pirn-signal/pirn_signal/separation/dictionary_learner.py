"""``DictionaryLearner`` — sparse-coding dictionary learning.

Algorithm:
    1. Receive the input signal frame, atom_count, sparsity_target, and max_iterations.
    2. Validate atom_count and sparsity_target (positive integers with
       sparsity_target <= atom_count) and max_iterations (positive integer).
    3. Initialize the dictionary with atom_count atoms of the same length as the signal frame.
    4. Alternate between sparse coding (OMP/LASSO) and dictionary update (MOD/K-SVD)
       until max_iterations is reached or convergence.
    5. Return a SourceFrame containing the learned dictionary (mixing_matrix_shape).

Math:
    K-SVD dictionary update objective:

    $$\\min_{D, X} \\|Y - DX\\|_F^2 \\quad \\text{s.t.} \\quad \\|x_i\\|_0 \\leq K_0 \\quad \\forall i$$

    where $D$ = dictionary with ``atom_count`` columns, $X$ = sparse codes, $K_0$ = sparsity_target.

References:
    - Aharon, M., Elad, M. & Bruckstein, A. (2006). "K-SVD: An Algorithm for Designing Overcomplete
      Dictionaries for Sparse Representation." IEEE Trans. Signal Process., 54(11), 4311-4322.
    - sklearn.decomposition.DictionaryLearning: https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.DictionaryLearning.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from sklearn.decomposition import DictionaryLearning

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


def _run_dictionary_learning(
    data: np.ndarray, atom_count: int, sparsity_target: int, max_iterations: int
) -> np.ndarray:
    dl = DictionaryLearning(  # type: ignore[call-overload]
        n_components=atom_count,
        alpha=int(sparsity_target),  # stubs expect int
        max_iter=max_iterations,
        random_state=0,
    )
    codes = dl.fit_transform(data.T)  # shape: (n_samples, atom_count)
    return codes.T  # shape: (atom_count, n_samples)


class DictionaryLearner(Knot):
    """Train an over-complete dictionary for sparse coding.

    Production needs ``sklearn.decomposition.DictionaryLearning``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        atom_count: Knot | int,
        sparsity_target: Knot | int,
        max_iterations: Knot | int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            atom_count=atom_count,
            sparsity_target=sparsity_target,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        atom_count: int,
        sparsity_target: int,
        max_iterations: int = 100,
        **_: Any,
    ) -> SourcePayload:
        """Train an over-complete dictionary from the signal and return a SourcePayload of learned codes.

        Args:
            signal: Multichannel signal used to train the sparse-coding dictionary.
            atom_count: Number of dictionary atoms to learn (positive integer).
            sparsity_target: L1 regularisation strength for sparse codes (positive integer,
                must not exceed atom_count).
            max_iterations: Maximum alternating optimisation iterations (positive integer).

        Returns:
            SourcePayload with ``source_count`` equal to ``atom_count`` and the corresponding
            mixing matrix shape.  The data array holds the learned code matrix
            (atom_count x n_samples).

        Raises:
            ValueError: If atom_count, sparsity_target, or max_iterations are invalid.
        """
        if not isinstance(atom_count, int) or atom_count <= 0:
            raise ValueError("DictionaryLearner: atom_count must be a positive integer")
        if not isinstance(sparsity_target, int) or sparsity_target <= 0:
            raise ValueError("DictionaryLearner: sparsity_target must be a positive integer")
        if sparsity_target > atom_count:
            raise ValueError("DictionaryLearner: sparsity_target must not exceed atom_count")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError("DictionaryLearner: max_iterations must be a positive integer")
        codes = await asyncio.to_thread(
            _run_dictionary_learning, signal.data, atom_count, sparsity_target, max_iterations
        )
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.frame.signal_id}:dict",
                source_count=atom_count,
                mixing_matrix_shape=(signal.frame.channel_count, atom_count),
            ),
            data=np.asarray(codes),
        )
