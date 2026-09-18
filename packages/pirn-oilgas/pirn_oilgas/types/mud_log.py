"""``MudLog`` — typed reference to a decoded mud log."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MudLog(PirnOpaqueValue):
    """Reference to a decoded mud log.

    The rows are not embedded; ``curves`` lists the mnemonics every row carries
    (ROP, gas units, lithology, …) and ``record_count`` how many depth records
    were decoded, so a downstream knot can reason about availability without
    materialising the rows. Mirrors :class:`~pirn_oilgas.types.las_file.LASFile`.
    """

    well_name: str = ""
    curves: tuple[str, ...] = ()
    record_count: int = 0
    depth_unit: str = "ft"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "well_name": self.well_name,
            "curves": list(self.curves),
            "record_count": self.record_count,
            "depth_unit": self.depth_unit,
            "fetched_at": self.fetched_at.isoformat(),
        }
