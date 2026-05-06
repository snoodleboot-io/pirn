"""``CellDetector`` — detect cells (nuclei) per WSI tile.

Production version uses StarDist / HoVerNet / Cellpose. This stub
returns a per-tile cell-count of 0.

Algorithm:
    1. Validate the tile sequence and model name.
    2. For each tile, run the configured cell-detection model.
    3. Return a mapping of (tile_x, tile_y) to detected cell count.

Math:
    Cell density per tile:

    $$d_t = \\frac{N_t}{A_t}$$

    where :math:`N_t` is the detected count and :math:`A_t` is the tile area.

References:
    - Schmidt, U., et al. (2018). Cell Detection with Star-convex Polygons. MICCAI.
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
        tiles: Knot | Sequence[WSITile],
        model_name: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tiles=tiles, model_name=model_name, _config=_config, **kwargs)

    async def process(
        self,
        tiles: Sequence[WSITile],
        model_name: str,
        **_: Any,
    ) -> Mapping[tuple[int, int], int]:
        """Detect cells in each WSI tile using the configured model.

        Args:
            tiles: Sequence of WSITile objects to process.
            model_name: Name of the cell-detection model to use.

        Returns:
            Mapping of (tile_x, tile_y) coordinate tuple to detected cell count.

        Raises:
            TypeError: If tiles is not a sequence or contains non-WSITile items.
            ValueError: If model_name is empty.
        """
        if not isinstance(tiles, (list, tuple)):
            raise TypeError("CellDetector: tiles must be a list or tuple")
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError("CellDetector: every tile must be WSITile")
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("CellDetector: model_name must be a non-empty string")
        return {(tile.tile_x, tile.tile_y): 0 for tile in tiles}
