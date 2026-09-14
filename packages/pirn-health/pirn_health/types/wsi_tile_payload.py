"""``WSITilePayload`` — WSI tile descriptor bundled with its pixel array.

``metadata`` carries the tile lineage metadata; ``data`` is the RGB pixel array
shaped ``(height, width, 3)``.  Both fields travel together through the
transport layer so downstream knots (CellDetector, TissueSegmenter,
MitosisCounter) receive the full picture in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_health.types.wsi_tile import WSITile


class WSITilePayload(Payload[WSITile, np.ndarray]):
    """WSI tile: descriptor metadata + RGB pixel array."""
