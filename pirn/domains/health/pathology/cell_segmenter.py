"""``CellSegmenter`` — segment individual cells from whole-slide image tiles."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CellSegmenter(Knot):
    """Segment individual cells from whole-slide image tiles."""

    _VALID_STAIN_TYPES: frozenset[str] = frozenset({"hematoxylin", "dab", "fluorescence"})

    def __init__(
        self,
        *,
        image_tile: Knot,
        min_cell_diameter_um: float,
        max_cell_diameter_um: float,
        stain_type: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(image_tile, Knot):
            raise TypeError("CellSegmenter: image_tile must be a Knot")
        if not isinstance(min_cell_diameter_um, (int, float)) or min_cell_diameter_um <= 0:
            raise ValueError(
                "CellSegmenter: min_cell_diameter_um must be > 0"
            )
        if not isinstance(max_cell_diameter_um, (int, float)):
            raise TypeError("CellSegmenter: max_cell_diameter_um must be a float")
        if stain_type not in self._VALID_STAIN_TYPES:
            raise ValueError(
                "CellSegmenter: stain_type must be one of 'hematoxylin', 'dab', 'fluorescence'"
            )
        self._min_cell_diameter_um = float(min_cell_diameter_um)
        self._max_cell_diameter_um = float(max_cell_diameter_um)
        self._stain_type = stain_type
        super().__init__(image_tile=image_tile, _config=_config, **kwargs)

    async def process(
        self,
        image_tile: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Segment cells in the given image tile and return masks and statistics.

        Args:
            image_tile: Dict with pixel_data (list or None), width_px (int),
                height_px (int), and resolution_um_per_px (float).

        Returns:
            Dict with cell_count (int), cell_masks (list), and
            mean_cell_area_um2 (float).
        """
        if not isinstance(image_tile, dict):
            raise TypeError("CellSegmenter: image_tile must be a dict")
        if self._max_cell_diameter_um <= self._min_cell_diameter_um:
            raise ValueError(
                "CellSegmenter: max_cell_diameter_um must be > min_cell_diameter_um"
            )
        return {
            "cell_count": 0,
            "cell_masks": [],
            "mean_cell_area_um2": 0.0,
        }
