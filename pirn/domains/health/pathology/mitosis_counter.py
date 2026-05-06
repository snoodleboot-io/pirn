"""``MitosisCounter`` — count mitotic figures across WSI tiles.

Production version uses MIDOG-style classifiers. This stub returns 0.

Algorithm:
    1. Validate tile sequence and confidence threshold.
    2. For each tile, run mitosis-figure detection at the given threshold.
    3. Return the summed count across all tiles.

Math:
    Total mitosis count:

    $$M = \\sum_{t} \\mathbf{1}[p_t \\geq \\tau]$$

    where p_t is the detection confidence and tau is the threshold.

References:
    - Aubreville, M., et al. (2023). MIDOG 2022 Challenge. arXiv:2301.07461.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile import WSITile


class MitosisCounter(Knot):
    """Count mitotic figures across the supplied WSI tiles."""

    def __init__(
        self,
        *,
        tiles: Knot | Sequence[WSITile],
        confidence_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tiles=tiles, confidence_threshold=confidence_threshold, _config=_config, **kwargs)

    async def process(
        self,
        tiles: Sequence[WSITile],
        confidence_threshold: float,
        **_: Any,
    ) -> int:
        """Count mitotic figures across all WSI tiles above the confidence threshold.

        Args:
            tiles: Sequence of WSITile objects to analyse.
            confidence_threshold: Minimum detection confidence in [0, 1].

        Returns:
            Total count of mitotic figures detected across all tiles.

        Raises:
            TypeError: If tiles is not a sequence or contains non-WSITile items.
            ValueError: If confidence_threshold is outside [0, 1].
        """
        if not isinstance(tiles, (list, tuple)):
            raise TypeError("MitosisCounter: tiles must be a list or tuple")
        for tile in tiles:
            if not isinstance(tile, WSITile):
                raise TypeError("MitosisCounter: every tile must be WSITile")
        if not isinstance(confidence_threshold, (int, float)):
            raise TypeError("MitosisCounter: confidence_threshold must be numeric")
        if not 0.0 <= float(confidence_threshold) <= 1.0:
            raise ValueError("MitosisCounter: confidence_threshold must be in [0, 1]")
        return 0
