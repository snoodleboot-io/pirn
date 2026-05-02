"""``WSITile`` — whole-slide-image tile descriptor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class WSITile(PirnOpaqueValue):
    """Single tile from a multi-resolution whole-slide image."""

    slide_id: str = ""
    tile_x: int = 0
    tile_y: int = 0
    level: int = 0
    width: int = 0
    height: int = 0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "level": self.level,
            "width": self.width,
            "height": self.height,
        }
