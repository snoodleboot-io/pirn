"""``AlignmentResult`` — where one trimmed read placed on the reference genome.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlignmentResult:
    seq_id: str
    contig: str
    position: int
    mapping_quality: int
    alignment_status: str  # "unique" | "multi" | "unaligned"
    trimmed_length: int
