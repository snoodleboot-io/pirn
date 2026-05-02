"""``CellDetector`` — detect cells (nuclei) per WSI tile.

Production version uses StarDist / HoVerNet / Cellpose. This stub
returns a per-tile cell-count of 0.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile import WSITile


class CellDetector(Knot):
    """Detect cells per WSI tile and return per-tile counts."""

    def __init__(
        self,
        *,
        tiles: Sequence[WSITile],
        model_name: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tiles, (list, tuple)):
            raise TypeError(
                "CellDetector: tiles must be a list or tuple"
            )
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError(
                    "CellDetector: every tile must be WSITile"
                )
        if not isinstance(model_name, str) or not model_name:
            raise ValueError(
                "CellDetector: model_name must be a non-empty string"
            )
        self._tiles = tuple(tiles)
        self._model_name = model_name
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[tuple[int, int], int]:
        return {(tile.tile_x, tile.tile_y): 0 for tile in self._tiles}
