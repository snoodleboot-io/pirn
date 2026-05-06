"""``DeviationSurvey`` — reference to a directional-drilling station table."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class DeviationSurvey(PirnOpaqueValue):
    """Directional-drilling deviation survey reference.

    ``station_count`` is the number of (md, inclination, azimuth) rows.
    """

    well_id: str = ""
    station_count: int = 0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.well_id,
            "station_count": self.station_count,
            "fetched_at": self.fetched_at.isoformat(),
        }
