"""``EvalMetrics`` — computed metric scores for an evaluation run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass
class EvalMetrics(PirnOpaqueValue):
    """Computed metric scores and optional details for an evaluation run."""

    scores: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def _pirn_audit_dict(self) -> dict:
        return {
            "scores": {k: float(v) for k, v in self.scores.items()},
            "details": dict(self.details),
        }
