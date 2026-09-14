"""``SplitManifest`` — train / validation / test partition of a ``DatasetManifest``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_ml.types.dataset_manifest import DatasetManifest


@dataclass(frozen=True)
class SplitManifest(PirnOpaqueValue):
    """Partition of a :class:`DatasetManifest` into train / validation / test."""

    train: DatasetManifest
    test: DatasetManifest
    validation: DatasetManifest | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "train": SplitManifest._nested_audit_dict(self.train),
            "validation": (
                None
                if self.validation is None
                else SplitManifest._nested_audit_dict(self.validation)
            ),
            "test": SplitManifest._nested_audit_dict(self.test),
        }

    @staticmethod
    def _nested_audit_dict(value: PirnOpaqueValue) -> Any:
        """The audit form of a nested partition, through the ``PirnOpaqueValue`` contract."""
        return value._pirn_audit_dict()
