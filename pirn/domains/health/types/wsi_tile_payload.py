"""``WSITilePayload`` — WSI tile descriptor bundled with its pixel array.

``tile`` carries the tile lineage metadata; ``pixels`` is the RGB pixel array
shaped ``(height, width, 3)``.  Both fields travel together through the
transport layer so downstream knots (CellDetector, TissueSegmenter,
MitosisCounter) receive the full picture in one input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.health.types.wsi_tile import WSITile


@dataclass
class WSITilePayload(PirnOpaqueValue):
    """WSI tile: descriptor metadata + RGB pixel array."""

    tile: WSITile
    pixels: np.ndarray

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.tile._pirn_audit_dict(),
            "pixels_shape": list(self.pixels.shape),
            "pixels_dtype": str(self.pixels.dtype),
        }
