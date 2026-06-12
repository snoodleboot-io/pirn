"""``FormationTop`` — single picked formation top in a well."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class FormationTop(PirnOpaqueValue):
    """A single formation top (picked horizon) in a well's measured-depth track."""

    well_id: str = ""
    formation_name: str = ""
    depth_md: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.well_id,
            "formation_name": self.formation_name,
            "depth_md": self.depth_md,
        }
