"""``PVTTable`` — pressure / volume / temperature lookup-table reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class PVTTable(PirnOpaqueValue):
    """Reference to a PVT lookup table for a fluid."""

    fluid_id: str = ""
    pressure_count: int = 0
    temperature_count: int = 0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "fluid_id": self.fluid_id,
            "pressure_count": self.pressure_count,
            "temperature_count": self.temperature_count,
        }
