"""``WellPath3D`` — reference to a computed 3-D well trajectory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class WellPath3D(PirnOpaqueValue):
    """Computed 3-D well-path reference.

    ``point_count`` is the number of (x, y, z) samples the underlying
    path table contains; the actual coordinate buffer is not embedded.
    """

    well_id: str = ""
    point_count: int = 0
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.well_id,
            "point_count": self.point_count,
            "fetched_at": self.fetched_at.isoformat(),
        }
