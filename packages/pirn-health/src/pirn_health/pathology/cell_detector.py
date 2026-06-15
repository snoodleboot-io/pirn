"""``CellDetector`` — detect cells (nuclei) per WSI tile.

Production version uses StarDist / HoVerNet / Cellpose. This implementation
estimates cell count from pixel variance as a proxy for nuclear density.

Algorithm:
    1. Validate the tile payload sequence and model name.
    2. For each tile, compute pixel variance as a proxy for detected cell count.
    3. Return a mapping of (tile_x, tile_y) to detected cell count.

Math:
    Cell density per tile:

    $$d_t = \\frac{N_t}{A_t}$$

    where :math:`N_t` is the detected count and :math:`A_t` is the tile area.

References:
    - Schmidt, U., et al. (2018). Cell Detection with Star-convex Polygons. MICCAI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.wsi_tile_payload import WSITilePayload


def _count_cells(payloads: Sequence[WSITilePayload]) -> Mapping[tuple[int, int], int]:
    result: dict[tuple[int, int], int] = {}
    for p in payloads:
        variance = float(np.var(p.pixels.astype(float)))
        count = int(variance * p.tile.width * p.tile.height / (255.0**2 + 1e-6))
        result[(p.tile.tile_x, p.tile.tile_y)] = count
    return result


class CellDetector(Knot):
    """Detect cells per WSI tile and return per-tile counts."""

    def __init__(
        self,
        *,
        tiles: Knot | Sequence[WSITilePayload],
        model_name: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tiles=tiles, model_name=model_name, _config=_config, **kwargs)

    async def process(
        self,
        tiles: Sequence[WSITilePayload],
        model_name: str,
        **_: Any,
    ) -> Mapping[tuple[int, int], int]:
        """Detect cells in each WSI tile using the configured model.

        Args:
            tiles: Sequence of WSITilePayload objects to process.
            model_name: Name of the cell-detection model to use.

        Returns:
            Mapping of (tile_x, tile_y) coordinate tuple to detected cell count.

        Raises:
            TypeError: If tiles is not a sequence or contains non-WSITilePayload items.
            ValueError: If model_name is empty.
        """
        if not isinstance(tiles, (list, tuple)):
            raise TypeError("CellDetector: tiles must be a list or tuple")
        for tile in tiles:
            if not isinstance(tile, WSITilePayload):
                raise TypeError("CellDetector: every tile must be WSITilePayload")
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("CellDetector: model_name must be a non-empty string")
        return await asyncio.to_thread(_count_cells, list(tiles))
