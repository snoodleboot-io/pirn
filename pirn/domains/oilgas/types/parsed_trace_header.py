"""``ParsedTraceHeader`` — flattened representation of a SEG-Y trace header."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ParsedTraceHeader(PirnOpaqueValue):
    """Selected fields parsed out of a binary SEG-Y trace header.

    Coordinate fields are floats expressed in the project CRS units.
    """

    inline: int = 0
    xline: int = 0
    cdp_x: float = 0.0
    cdp_y: float = 0.0
    source_x: float = 0.0
    source_y: float = 0.0
    receiver_x: float = 0.0
    receiver_y: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "inline": self.inline,
            "xline": self.xline,
            "cdp_x": self.cdp_x,
            "cdp_y": self.cdp_y,
            "source_x": self.source_x,
            "source_y": self.source_y,
            "receiver_x": self.receiver_x,
            "receiver_y": self.receiver_y,
        }
