"""``EvalReport`` — metrics computed for a model on a dataset."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvalReport(PirnOpaqueValue):
    """Numeric metrics + free-form details for a single evaluation run."""

    model_id: str = ""
    dataset_name: str = ""
    metrics: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation."""
        return {
            "model_id": self.model_id,
            "dataset_name": self.dataset_name,
            "metrics": {k: float(v) for k, v in self.metrics.items()},
            "details": dict(self.details),
            "evaluated_at": self.evaluated_at.isoformat(),
        }
