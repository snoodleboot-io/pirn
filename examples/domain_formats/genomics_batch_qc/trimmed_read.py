"""``TrimmedRead`` — a read after adapter and low-quality base trimming.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrimmedRead:
    seq_id: str
    original_length: int
    trimmed_sequence: str
    trimmed_quality: str
    adapter_found: bool
    bases_trimmed: int
