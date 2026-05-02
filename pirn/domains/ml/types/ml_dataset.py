"""``MLDataset`` — a typed reference to an ML training/eval dataset.

The dataset's actual rows are not embedded in this value; the value is
a *reference* (logical name + provenance) that downstream knots resolve
when they need to materialise the data. This keeps content-addressing
cheap and avoids accidental memory bloat in lineage records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MLDataset(PirnOpaqueValue):
    """Reference to a dataset shaped for ML consumption."""

    name: str = ""
    feature_names: tuple[str, ...] = ()
    target_name: str | None = None
    row_count: int = 0
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation."""
        return {
            "name": self.name,
            "feature_names": list(self.feature_names),
            "target_name": self.target_name,
            "row_count": self.row_count,
            "source_uri": self.source_uri,
            "fetched_at": self.fetched_at.isoformat(),
        }
