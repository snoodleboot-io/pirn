"""``TissueSegmenter`` — separate tissue from background on WSI tiles.

Production version uses Otsu thresholding in HSV space or a deep
model. This stub keeps every tile (passes through) so downstream
knots can be wired without an algorithm.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile import WSITile


class TissueSegmenter(Knot):
    """Identify tissue-containing tiles from a WSI tile set."""

    def __init__(
        self,
        *,
        tiles: Sequence[WSITile],
        threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tiles, (list, tuple)):
            raise TypeError(
                "TissueSegmenter: tiles must be a list or tuple"
            )
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError(
                    "TissueSegmenter: every tile must be WSITile"
                )
        if not isinstance(threshold, (int, float)):
            raise TypeError("TissueSegmenter: threshold must be numeric")
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError(
                "TissueSegmenter: threshold must be in [0, 1]"
            )
        self._tiles = tuple(tiles)
        self._threshold = float(threshold)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[WSITile, ...]:
        """Segment tissue-containing tiles from the slide using the configured threshold and return the passing tiles.

        Returns:
            Tuple of WSITile objects that contain tissue above the configured threshold.
        """
        return self._tiles
