"""``RunSummary`` — run-level aggregate of every read's QC and alignment.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunSummary:
    total_reads: int
    pass_qc: int
    trimmed_count: int
    aligned_count: int
    mean_quality: float
    gc_content: float
    alignment_rate: float
