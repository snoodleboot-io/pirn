"""``FittedEstimator`` — wrapper around a fitted sklearn-compatible model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass
class FittedEstimator(PirnOpaqueValue):
    """Fitted sklearn-compatible estimator object."""

    estimator: Any
    algorithm: str = ""

    def _pirn_audit_dict(self) -> dict:
        return {"algorithm": self.algorithm}
