"""``NMFDecomposer`` — non-negative matrix factorisation."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class NMFDecomposer(Knot):
    """Non-negative matrix factorisation.

    Production needs ``sklearn.decomposition.NMF``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: int,
        max_iterations: int = 200,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError(
                "NMFDecomposer: component_count must be a positive integer"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "NMFDecomposer: max_iterations must be a positive integer"
            )
        self._component_count = component_count
        self._max_iterations = max_iterations
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def component_count(self) -> int:
        return self._component_count

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._component_count,
            mixing_matrix_shape=(signal.channel_count, self._component_count),
        )
