"""``DataSplit`` — train / validation / test partition of an ``MLDataset``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.ml.types.ml_dataset import MLDataset


@dataclass(frozen=True)
class DataSplit(PirnOpaqueValue):
    """Partition of an :class:`MLDataset` into train / validation / test."""

    train: MLDataset
    test: MLDataset
    validation: MLDataset | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation."""
        return {
            "train": self.train._pirn_audit_dict(),
            "validation": (None if self.validation is None else self.validation._pirn_audit_dict()),
            "test": self.test._pirn_audit_dict(),
        }
