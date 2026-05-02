"""``GenomicsRecord`` — single sample/locus genotype snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class GenomicsRecord(PirnOpaqueValue):
    """Per-sample, per-locus genotype call with quality."""

    sample_id: str = ""
    locus: str = ""
    genotype: str = ""
    quality_score: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "locus": self.locus,
            "genotype": self.genotype,
            "quality_score": self.quality_score,
        }
