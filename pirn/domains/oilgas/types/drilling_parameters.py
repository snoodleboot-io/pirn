"""``DrillingParameters`` — reference to a depth-indexed drilling-parameter table."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class DrillingParameters(PirnOpaqueValue):
    """Depth-indexed drilling-parameter reference.

    The actual columns (WOB, RPM, ROP, mud weight, ECD, ...) live in the
    underlying frame; ``depth_count`` records how many depth samples
    were ingested.
    """

    well_id: str = ""
    depth_count: int = 0
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.well_id,
            "depth_count": self.depth_count,
            "fetched_at": self.fetched_at.isoformat(),
        }
