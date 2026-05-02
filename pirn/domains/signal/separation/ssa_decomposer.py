"""``SSADecomposer`` — singular spectrum analysis."""

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
        embedding_dim: int,
        component_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._embedding_dim = embedding_dim
        self._component_count = component_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def component_count(self) -> int:
        return self._component_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._component_count,
            mixing_matrix_shape=(self._embedding_dim, self._component_count),
        )
