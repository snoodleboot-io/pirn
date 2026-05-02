"""``SegyTrace`` — a single SEG-Y trace reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SegyTrace(PirnOpaqueValue):
    """One trace's metadata. Sample buffer is not embedded."""

    trace_id: str = ""
    sample_count: int = 0
    sample_interval_ms: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "sample_count": self.sample_count,
            "sample_interval_ms": self.sample_interval_ms,
        }
