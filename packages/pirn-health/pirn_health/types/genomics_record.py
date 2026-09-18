"""``GenomicsRecord`` — single sample/locus genotype snapshot.

PHI safety:
    ``sample_id`` never appears in :meth:`_pirn_audit_dict`: the audit dict is
    what the lineage store, emitters and content hasher persist, and a sample
    identifier is a direct identifier under HIPAA Safe Harbor. The audit dict
    carries ``sample_id_hash`` instead — a stable
    :class:`~pirn.core.content_hasher.ContentHasher` digest, so two samples
    remain distinguishable (and cannot collide into one lineage identity)
    without the raw value being written anywhere. The digest is a pseudonym
    for joining, not de-identified data for export: exports go through
    :class:`~pirn_health.clinical.phi_redactor.PHIRedactor`, which keys its
    tokens on a deployment salt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.content_hasher import ContentHasher
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
            "sample_id_hash": ContentHasher.hash(self.sample_id),
            "locus": self.locus,
            "genotype": self.genotype,
            "quality_score": self.quality_score,
        }
