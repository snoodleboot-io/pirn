"""``SpectrumFrame`` — typed reference to a frequency-domain representation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SpectrumFrame(PirnOpaqueValue):
    """Reference to a discrete frequency-domain spectrum."""

    signal_id: str = ""
    frequency_bins: int = 0
    frequency_resolution_hz: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "frequency_bins": self.frequency_bins,
            "frequency_resolution_hz": self.frequency_resolution_hz,
        }
