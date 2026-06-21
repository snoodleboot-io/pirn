"""``SplitArrays`` — train/test feature and target arrays."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass
class SplitArrays(PirnOpaqueValue):
    """Train and test feature/target arrays."""

    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray | None = None
    y_test: np.ndarray | None = None

    def _pirn_audit_dict(self) -> dict:
        return {
            "train_rows": int(self.X_train.shape[0]),
            "test_rows": int(self.X_test.shape[0]),
        }
