"""``ScadaTimeSeries`` — reference to a SCADA / historian sensor stream."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ScadaTimeSeries(PirnOpaqueValue):
    """Reference to a sampled SCADA / historian sensor channel."""

    sensor_id: str = ""
    sample_count: int = 0
    sample_interval_sec: float = 0.0
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sample_count": self.sample_count,
            "sample_interval_sec": self.sample_interval_sec,
            "fetched_at": self.fetched_at.isoformat(),
        }
