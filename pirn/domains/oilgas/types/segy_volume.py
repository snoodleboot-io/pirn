"""``SegyVolume`` — typed reference to a 3-D SEG-Y seismic volume."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SegyVolume(PirnOpaqueValue):
    """Reference to a SEG-Y seismic volume.

    The actual sample buffer is not embedded; only its shape and a
    fetched-at timestamp travel through the lineage. Real readers
    (``segyio``) are loaded by knot implementations, not by this type.
    """

    volume_id: str = ""
    inline_count: int = 0
    xline_count: int = 0
    sample_count: int = 0
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "volume_id": self.volume_id,
            "inline_count": self.inline_count,
            "xline_count": self.xline_count,
            "sample_count": self.sample_count,
            "fetched_at": self.fetched_at.isoformat(),
        }
