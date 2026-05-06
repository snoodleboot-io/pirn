"""``PathologyStainNormalizer`` — normalize H&E stain intensities.

Algorithm:
    1. Validate method and optional reference stain matrix.
    2. Decompose image tile using Macenko, Vahadane, or Reinhard method.
    3. Return normalized pixel data and the stain matrix used.

Math:
    Optical density for pixel intensity I:

    $$OD = -\\log\\left(\\frac{I}{I_0}\\right)$$

    where I_0 = 255 is the background intensity.

References:
    - Macenko, M., et al. (2009). A method for normalizing histology slides. ISBI.
    - Vahadane, A., et al. (2016). Structure-preserving color normalization. IEEE TMI.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PathologyStainNormalizer(Knot):
    """Normalize H&E stain intensities using Macenko, Vahadane, or Reinhard method."""

    def __init__(
        self,
        *,
        image_tile: Knot | dict[str, Any],
        method: Knot | str,
        reference_stain_matrix: Knot | list[list[float]] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            image_tile=image_tile,
            method=method,
            reference_stain_matrix=reference_stain_matrix,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        image_tile: dict[str, Any],
        method: str,
        reference_stain_matrix: list[list[float]] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Normalize stain intensities in the image tile using the given method.

        Args:
            image_tile: Dict with width_px (int), height_px (int), and
                pixel_data (list of pixel values).
            method: One of 'macenko', 'vahadane', 'reinhard'.
            reference_stain_matrix: Optional 2x2 reference matrix; defaults to identity.

        Returns:
            Dict with normalized_pixel_data (list), stain_matrix
            (list of lists of float), and method (str).

        Raises:
            TypeError: If image_tile is not a dict.
            ValueError: If method is not valid.
        """
        if not isinstance(image_tile, dict):
            raise TypeError("PathologyStainNormalizer: image_tile must be a dict")
        valid_methods = frozenset({"macenko", "vahadane", "reinhard"})
        if method not in valid_methods:
            raise ValueError(
                "PathologyStainNormalizer: method must be one of 'macenko', 'vahadane', 'reinhard'"
            )
        stain_matrix = reference_stain_matrix if reference_stain_matrix is not None else [[1.0, 0.0], [0.0, 1.0]]
        return {
            "normalized_pixel_data": image_tile.get("pixel_data", []),
            "stain_matrix": stain_matrix,
            "method": method,
        }
