"""``WSITileExtractor`` — extract tiles from a whole-slide image.

Production version uses ``openslide`` / ``tifffile`` to stream tiles
at the requested level. This stub returns a deterministic grid of
:class:`WSITile` descriptors.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile import WSITile


class WSITileExtractor(Knot):
    """Generate :class:`WSITile` descriptors over a slide grid."""

    def __init__(
        self,
        *,
        slide_id: str,
        level: int,
        tile_size: int,
        grid_rows: int,
        grid_cols: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(slide_id, str) or not slide_id:
            raise ValueError(
                "WSITileExtractor: slide_id must be a non-empty string"
            )
        for label, value in (
            ("level", level),
            ("tile_size", tile_size),
            ("grid_rows", grid_rows),
            ("grid_cols", grid_cols),
        ):
            if not isinstance(value, int):
                raise TypeError(
                    f"WSITileExtractor: {label} must be int"
                )
        if level < 0:
            raise ValueError("WSITileExtractor: level must be >= 0")
        for label, value in (
            ("tile_size", tile_size),
            ("grid_rows", grid_rows),
            ("grid_cols", grid_cols),
        ):
            if value <= 0:
                raise ValueError(
                    f"WSITileExtractor: {label} must be positive"
                )
        self._slide_id = slide_id
        self._level = level
        self._tile_size = tile_size
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[WSITile, ...]:
        """Generate a grid of WSITile descriptors for the configured slide at the configured level and tile size.

        Returns:
            Tuple of WSITile descriptors covering the full grid_rows x grid_cols grid.
        """
        return tuple(
            WSITile(
                slide_id=self._slide_id,
                tile_x=col * self._tile_size,
                tile_y=row * self._tile_size,
                level=self._level,
                width=self._tile_size,
                height=self._tile_size,
            )
            for row in range(self._grid_rows)
            for col in range(self._grid_cols)
        )
