"""``TissueSegmenter`` — separate tissue from background on WSI tiles.

Production version uses Otsu thresholding in HSV space or a deep
model. This stub keeps every tile (passes through) so downstream
knots can be wired without an algorithm.

Algorithm:
    1. Validate tile sequence and threshold.
    2. Apply tissue-vs-background segmentation per tile.
    3. Return tiles whose tissue fraction exceeds the threshold.

Math:
    Tissue fraction for tile t:

    $$f_t = \\frac{|\\{p : I_p < \\tau\\}|}{W \\times H}$$

    where I_p is pixel intensity and tau is the threshold.

References:
    - Otsu, N. (1979). A threshold selection method from gray-level histograms. IEEE TSMC.
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
        tiles: Knot | Sequence[WSITile],
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tiles=tiles, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        tiles: Sequence[WSITile],
        threshold: float,
        **_: Any,
    ) -> tuple[WSITile, ...]:
        """Segment tissue-containing tiles from the slide using the threshold.

        Args:
            tiles: Sequence of WSITile objects.
            threshold: Tissue-fraction threshold in [0, 1].

        Returns:
            Tuple of WSITile objects that contain tissue above the threshold.

        Raises:
            TypeError: If tiles is not a sequence or contains non-WSITile items.
            ValueError: If threshold is outside [0, 1].
        """
        if not isinstance(tiles, (list, tuple)):
            raise TypeError("TissueSegmenter: tiles must be a list or tuple")
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError("TissueSegmenter: every tile must be WSITile")
        if not isinstance(threshold, (int, float)):
            raise TypeError("TissueSegmenter: threshold must be numeric")
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("TissueSegmenter: threshold must be in [0, 1]")
        return tuple(tiles)
