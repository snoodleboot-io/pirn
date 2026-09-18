"""``ReadQC`` — per-read quality metrics and pass/fail classification.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReadQC:
    seq_id: str
    mean_quality: float
    gc_content: float  # fraction 0.0-1.0
    n_fraction: float  # fraction 0.0-1.0
    pass_qc: bool
    fail_reason: str  # empty string when pass_qc is True
