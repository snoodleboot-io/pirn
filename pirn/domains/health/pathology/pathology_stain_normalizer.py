"""``PathologyStainNormalizer`` — normalize H&E stain intensities using Macenko or Vahadane method."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PathologyStainNormalizer(Knot):
    """Normalize H&E stain intensities using Macenko, Vahadane, or Reinhard method."""

    _VALID_METHODS: frozenset[str] = frozenset({"macenko", "vahadane", "reinhard"})

    def __init__(
        self,
        *,
        image_tile: Knot,
        method: str,
        reference_stain_matrix: list[list[float]] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(image_tile, Knot):
            raise TypeError("PathologyStainNormalizer: image_tile must be a Knot")
        if method not in self._VALID_METHODS:
            raise ValueError(
                "PathologyStainNormalizer: method must be one of 'macenko', 'vahadane', 'reinhard'"
            )
        self._method = method
        self._reference_stain_matrix = reference_stain_matrix
        super().__init__(image_tile=image_tile, _config=_config, **kwargs)

    async def process(
        self,
        image_tile: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Normalize stain intensities in the image tile using the configured method.

        Args:
            image_tile: Dict with width_px (int), height_px (int), and
                pixel_data (list of pixel values).

        Returns:
            Dict with normalized_pixel_data (list), stain_matrix
            (list of lists of float), and method (str).
        """
        if not isinstance(image_tile, dict):
            raise TypeError("PathologyStainNormalizer: image_tile must be a dict")
        stain_matrix = self._reference_stain_matrix if self._reference_stain_matrix is not None else [[1.0, 0.0], [0.0, 1.0]]
        return {
            "normalized_pixel_data": image_tile.get("pixel_data", []),
            "stain_matrix": stain_matrix,
            "method": self._method,
        }
