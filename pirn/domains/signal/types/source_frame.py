"""``SourceFrame`` — typed reference to a source-separation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SourceFrame(PirnOpaqueValue):
    """Reference to source signals recovered by a separation algorithm."""

    signal_id: str = ""
    source_count: int = 0
    mixing_matrix_shape: tuple[int, int] = (0, 0)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source_count": self.source_count,
            "mixing_matrix_shape": list(self.mixing_matrix_shape),
        }
