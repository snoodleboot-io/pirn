"""``WSITileExtractor`` — extract tiles from a whole-slide image.

Production version uses ``openslide`` / ``tifffile`` to stream tiles
at the requested level. This stub returns a deterministic grid of
:class:`WSITile` descriptors.

Algorithm:
    1. Validate slide_id, level, tile_size, grid_rows, and grid_cols.
    2. Generate a grid_rows x grid_cols grid of WSITile descriptors.
    3. Return the full grid as a tuple.

Math:
    Tile origin for grid position (r, c):

    $$x = c \\times s, \\quad y = r \\times s$$

    where s is the tile size in pixels.

References:
    - Goode, A., et al. (2013). OpenSlide: A vendor-neutral software foundation for digital pathology. JPI.
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
        slide_id: Knot | str,
        level: Knot | int,
        tile_size: Knot | int,
        grid_rows: Knot | int,
        grid_cols: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            slide_id=slide_id,
            level=level,
            tile_size=tile_size,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        slide_id: str,
        level: int,
        tile_size: int,
        grid_rows: int,
        grid_cols: int,
        **_: Any,
    ) -> tuple[WSITile, ...]:
        """Generate a grid of WSITile descriptors for the configured slide.

        Args:
            slide_id: Non-empty slide identifier string.
            level: Pyramid level (>= 0).
            tile_size: Tile side length in pixels (> 0).
            grid_rows: Number of rows in the grid (> 0).
            grid_cols: Number of columns in the grid (> 0).

        Returns:
            Tuple of WSITile descriptors covering the full grid_rows x grid_cols grid.

        Raises:
            ValueError: If slide_id is empty, level < 0, or any positive-int param is <= 0.
            TypeError: If any int param is not an int.
        """
        if not isinstance(slide_id, str) or not slide_id:
            raise ValueError("WSITileExtractor: slide_id must be a non-empty string")
        for label, value in (
            ("level", level),
            ("tile_size", tile_size),
            ("grid_rows", grid_rows),
            ("grid_cols", grid_cols),
        ):
            if not isinstance(value, int):
                raise TypeError(f"WSITileExtractor: {label} must be int")
        if level < 0:
            raise ValueError("WSITileExtractor: level must be >= 0")
        for label, value in (
            ("tile_size", tile_size),
            ("grid_rows", grid_rows),
            ("grid_cols", grid_cols),
        ):
            if value <= 0:
                raise ValueError(f"WSITileExtractor: {label} must be positive")
        return tuple(
            WSITile(
                slide_id=slide_id,
                tile_x=col * tile_size,
                tile_y=row * tile_size,
                level=level,
                width=tile_size,
                height=tile_size,
            )
            for row in range(grid_rows)
            for col in range(grid_cols)
        )
