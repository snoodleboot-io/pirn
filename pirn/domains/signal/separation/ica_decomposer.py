"""``ICADecomposer`` — independent component analysis."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class ICADecomposer(Knot):
    """FastICA-style independent component analysis.

    Production needs ``sklearn.decomposition.FastICA``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        source_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_count, int) or source_count <= 0:
            raise ValueError(
                "ICADecomposer: source_count must be a positive integer"
            )
        self._source_count = source_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def source_count(self) -> int:
        return self._source_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._source_count,
            mixing_matrix_shape=(signal.channel_count, self._source_count),
        )
