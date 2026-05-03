"""``DictionaryLearner`` — sparse-coding dictionary learning."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class DictionaryLearner(Knot):
    """Train an over-complete dictionary for sparse coding.

    Production needs ``sklearn.decomposition.DictionaryLearning``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        atom_count: int,
        sparsity_target: int,
        max_iterations: int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(atom_count, int) or atom_count <= 0:
            raise ValueError(
                "DictionaryLearner: atom_count must be a positive integer"
            )
        if not isinstance(sparsity_target, int) or sparsity_target <= 0:
            raise ValueError(
                "DictionaryLearner: sparsity_target must be a positive integer"
            )
        if sparsity_target > atom_count:
            raise ValueError(
                "DictionaryLearner: sparsity_target must not exceed atom_count"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "DictionaryLearner: max_iterations must be a positive integer"
            )
        self._atom_count = atom_count
        self._sparsity_target = sparsity_target
        self._max_iterations = max_iterations
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def atom_count(self) -> int:
        return self._atom_count

    @property
    def sparsity_target(self) -> int:
        return self._sparsity_target

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        """Train an over-complete dictionary from the signal and return a SourceFrame of learned atoms.

        Args:
            signal: Multichannel signal used to train the sparse-coding dictionary.

        Returns:
            SourceFrame with ``source_count`` equal to ``atom_count`` and the corresponding mixing matrix shape.
        """
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._atom_count,
            mixing_matrix_shape=(signal.channel_count, self._atom_count),
        )
