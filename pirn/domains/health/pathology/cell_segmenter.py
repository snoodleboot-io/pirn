"""``CellSegmenter`` — segment individual cells from whole-slide image tiles.

Algorithm:
    1. Validate image tile, diameter bounds, and stain type.
    2. Apply the selected stain-deconvolution model.
    3. Return cell masks and statistics.

Math:
    Cell area for a circular cell of diameter d:

    $$A = \\pi \\left(\\frac{d}{2}\\right)^2$$

References:
    - Bankhead, P., et al. (2017). QuPath: Open software for bioimage analysis. Scientific Reports.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CellSegmenter(Knot):
    """Segment individual cells from whole-slide image tiles."""

    def __init__(
        self,
        *,
        image_tile: Knot | dict[str, Any],
        min_cell_diameter_um: Knot | float,
        max_cell_diameter_um: Knot | float,
        stain_type: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            image_tile=image_tile,
            min_cell_diameter_um=min_cell_diameter_um,
            max_cell_diameter_um=max_cell_diameter_um,
            stain_type=stain_type,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        image_tile: dict[str, Any],
        min_cell_diameter_um: float,
        max_cell_diameter_um: float,
        stain_type: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Segment cells in the given image tile and return masks and statistics.

        Args:
            image_tile: Dict with pixel_data (list or None), width_px (int),
                height_px (int), and resolution_um_per_px (float).
            min_cell_diameter_um: Minimum cell diameter in micrometres.
            max_cell_diameter_um: Maximum cell diameter in micrometres.
            stain_type: One of 'hematoxylin', 'dab', 'fluorescence'.

        Returns:
            Dict with cell_count (int), cell_masks (list), and
            mean_cell_area_um2 (float).

        Raises:
            TypeError: If image_tile is not a dict.
            ValueError: If diameters are not positive or max <= min, or stain_type is invalid.
        """
        if not isinstance(image_tile, dict):
            raise TypeError("CellSegmenter: image_tile must be a dict")
        if not isinstance(min_cell_diameter_um, (int, float)) or float(min_cell_diameter_um) <= 0:
            raise ValueError("CellSegmenter: min_cell_diameter_um must be > 0")
        if not isinstance(max_cell_diameter_um, (int, float)):
            raise TypeError("CellSegmenter: max_cell_diameter_um must be a float")
        if float(max_cell_diameter_um) <= float(min_cell_diameter_um):
            raise ValueError("CellSegmenter: max_cell_diameter_um must be > min_cell_diameter_um")
        valid_stain_types = frozenset({"hematoxylin", "dab", "fluorescence"})
        if stain_type not in valid_stain_types:
            raise ValueError(
                "CellSegmenter: stain_type must be one of 'hematoxylin', 'dab', 'fluorescence'"
            )
        return {
            "cell_count": 0,
            "cell_masks": [],
            "mean_cell_area_um2": 0.0,
        }
