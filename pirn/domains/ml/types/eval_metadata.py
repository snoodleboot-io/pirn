"""``EvalMetadata`` — provenance descriptor for a single evaluation run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvalMetadata(PirnOpaqueValue):
    """Provenance fields for an evaluation run (no metric scores)."""

    model_id: str = ""
    dataset_name: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "dataset_name": self.dataset_name,
            "evaluated_at": self.evaluated_at.isoformat(),
        }
