"""``MitosisCounter`` — count mitotic figures across WSI tiles.

Production version uses MIDOG-style classifiers. This stub returns 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile import WSITile


class MitosisCounter(Knot):
    """Count mitotic figures across the supplied WSI tiles."""

    def __init__(
        self,
        *,
        tiles: Sequence[WSITile],
        confidence_threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tiles, (list, tuple)):
            raise TypeError(
                "MitosisCounter: tiles must be a list or tuple"
            )
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError(
                    "MitosisCounter: every tile must be WSITile"
                )
        if not isinstance(confidence_threshold, (int, float)):
            raise TypeError(
                "MitosisCounter: confidence_threshold must be numeric"
            )
        if not 0.0 <= float(confidence_threshold) <= 1.0:
            raise ValueError(
                "MitosisCounter: confidence_threshold must be in [0, 1]"
            )
        self._tiles = tuple(tiles)
        self._confidence_threshold = float(confidence_threshold)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> int:
        return 0
