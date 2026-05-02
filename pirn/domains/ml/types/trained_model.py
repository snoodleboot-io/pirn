"""``TrainedModel`` — a reference to a trained model artifact.

The artifact bytes are not embedded; the value is a logical reference
that downstream knots resolve via the registered model id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class TrainedModel(PirnOpaqueValue):
    """Reference to a trained model artifact."""

    model_id: str = ""
    algorithm: str = ""
    hyperparameters: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    feature_names: tuple[str, ...] = ()
    target_name: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation."""
        return {
            "model_id": self.model_id,
            "algorithm": self.algorithm,
            "hyperparameters": dict(self.hyperparameters),
            "feature_names": list(self.feature_names),
            "target_name": self.target_name,
            "created_at": self.created_at.isoformat(),
        }
