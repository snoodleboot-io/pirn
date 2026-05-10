"""``MLFeatures`` — feature matrix and optional target vector for an ML dataset."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass
class MLFeatures(PirnOpaqueValue):
    """Feature matrix X and optional target vector y."""

    X: np.ndarray
    y: np.ndarray | None = None

    def _pirn_audit_dict(self) -> dict:
        return {"n_rows": int(self.X.shape[0]), "n_features": int(self.X.shape[1])}
