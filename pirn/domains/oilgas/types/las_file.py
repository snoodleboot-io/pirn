"""``LASFile`` — typed reference to a parsed LAS well-log file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LASFile(PirnOpaqueValue):
    """Reference to a parsed LAS file.

    The curve buffers are not embedded; ``curves`` lists the curve
    mnemonics so that downstream knots can reason about availability
    without having to materialise the data.
    """

    well_id: str = ""
    curves: tuple[str, ...] = ()
    depth_unit: str = "m"
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.well_id,
            "curves": list(self.curves),
            "depth_unit": self.depth_unit,
            "fetched_at": self.fetched_at.isoformat(),
        }
