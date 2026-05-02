"""``PCADecomposer`` — principal component analysis on a multichannel signal."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class PCADecomposer(Knot):
    """Principal component analysis decomposition.

    Production needs ``sklearn.decomposition.PCA``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: int,
        whiten: bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError(
                "PCADecomposer: component_count must be a positive integer"
            )
        if not isinstance(whiten, bool):
            raise TypeError("PCADecomposer: whiten must be a bool")
        self._component_count = component_count
        self._whiten = whiten
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def component_count(self) -> int:
        return self._component_count

    @property
    def whiten(self) -> bool:
        return self._whiten

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SourceFrame:
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=self._component_count,
            mixing_matrix_shape=(signal.channel_count, self._component_count),
        )
