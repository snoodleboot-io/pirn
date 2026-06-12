"""``SplitManifest`` — train / validation / test partition of a ``DatasetManifest``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.ml.types.dataset_manifest import DatasetManifest


@dataclass(frozen=True)
class SplitManifest(PirnOpaqueValue):
    """Partition of a :class:`DatasetManifest` into train / validation / test."""

    train: DatasetManifest
    test: DatasetManifest
    validation: DatasetManifest | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "train": self.train._pirn_audit_dict(),
            "validation": (None if self.validation is None else self.validation._pirn_audit_dict()),
            "test": self.test._pirn_audit_dict(),
        }
