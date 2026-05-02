"""``SparseDecomposer`` — sparse decomposition over a fixed dictionary."""

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

    def __init__(
        self,
        *,
        signal: Knot,
        atom_count: int,
        sparsity_target: int,
        algorithm: str = "omp",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(atom_count, int) or atom_count <= 0:
            raise ValueError(
                "SparseDecomposer: atom_count must be a positive integer"
            )
        if not isinstance(sparsity_target, int) or sparsity_target <= 0:
            raise ValueError(
                "SparseDecomposer: sparsity_target must be a positive integer"
            )
        if algorithm not in {"omp", "lasso", "lars"}:
            raise ValueError(
                "SparseDecomposer: algorithm must be 'omp', 'lasso', or 'lars'"
            )
        self._atom_count = atom_count
        self._sparsity_target = sparsity_target
        self._algorithm = algorithm
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def atom_count(self) -> int:
        return self._atom_count

    @property
    def sparsity_target(self) -> int:
        return self._sparsity_target

    @property
    def algorithm(self) -> str:
        return self._algorithm

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._sparsity_target,
            mixing_matrix_shape=(signal.channel_count, self._atom_count),
        )
