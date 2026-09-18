"""``FastqRead`` — one raw sequencing read as decoded from a FASTQ record.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FastqRead:
    seq_id: str
    description: str
    sequence: str
    quality: str  # ASCII Phred+33 quality string, same length as sequence
