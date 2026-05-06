"""``WaveletFrame`` — typed reference to a wavelet-domain decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class WaveletFrame(PirnOpaqueValue):
    """Reference to a wavelet-domain decomposition of a signal."""

    signal_id: str = ""
    wavelet_name: str = ""
    scale_count: int = 0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "wavelet_name": self.wavelet_name,
            "scale_count": self.scale_count,
        }
