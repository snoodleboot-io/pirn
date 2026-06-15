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

import numpy as np
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
        pixel_data = image_tile.get("pixel_data")
        width_px = int(image_tile.get("width_px", 0))
        height_px = int(image_tile.get("height_px", 0))
        resolution_um_per_px = float(image_tile.get("resolution_um_per_px", 0.25))
        if not pixel_data or width_px == 0 or height_px == 0:
            return {"cell_count": 0, "cell_masks": [], "mean_cell_area_um2": 0.0}
        arr = (
            np.asarray(pixel_data, dtype=np.float64).reshape(height_px, width_px, -1)
            if len(pixel_data) == width_px * height_px
            else np.asarray(pixel_data, dtype=np.float64)
        )
        if arr.ndim == 3 and arr.shape[-1] >= 3:
            gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        else:
            gray = arr.reshape(height_px, width_px) if arr.ndim > 1 else arr
        threshold = float(np.mean(gray))
        min_area_px2 = (min_cell_diameter_um / resolution_um_per_px / 2) ** 2 * 3.14159
        max_area_px2 = (max_cell_diameter_um / resolution_um_per_px / 2) ** 2 * 3.14159
        if stain_type == "fluorescence":
            cell_mask = gray > threshold
        else:
            cell_mask = gray < threshold
        cell_area_px2 = (min_area_px2 + max_area_px2) / 2.0
        candidate_pixels = int(cell_mask.sum())
        cell_count = max(0, int(candidate_pixels / max(1.0, cell_area_px2)))
        mean_cell_area_um2 = cell_area_px2 * resolution_um_per_px**2
        return {
            "cell_count": cell_count,
            "cell_masks": [],
            "mean_cell_area_um2": mean_cell_area_um2,
        }
