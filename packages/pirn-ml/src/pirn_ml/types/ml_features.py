"""``MLFeatures`` — feature matrix and optional target vector for an ML dataset."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass
class MLFeatures(PirnOpaqueValue):
    """Feature matrix and optional target vector."""

    feature_matrix: np.ndarray
    target_vector: np.ndarray | None = None

    def _pirn_audit_dict(self) -> dict:
        return {
            "n_rows": int(self.feature_matrix.shape[0]),
            "n_features": int(self.feature_matrix.shape[1]),
        }
