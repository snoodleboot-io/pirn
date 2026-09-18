"""``SequencingConfig`` — the thresholds and reference data the QC stages share.

Part of the ``examples.domain_formats.genomics_batch_qc`` example.
"""

from __future__ import annotations

from typing import ClassVar


class SequencingConfig:
    """Fixed run configuration shared by the QC, trim, align and synthesis stages."""

    known_adapter: ClassVar[str] = "AGATCGGAAGAGC"
    low_quality_threshold: ClassVar[int] = 20
    min_read_length: ClassVar[int] = 20
    no_call_base: ClassVar[str] = "N"
    bases: ClassVar[str] = "ATGCN"
    contigs: ClassVar[tuple[str, ...]] = ("chr1", "chr2", "chr3", "chr4", "chrX", "chrY", "chrM")

    @staticmethod
    def called_bases() -> str:
        """The alphabet without the ``N`` no-call base, used to draw clean reads."""
        return SequencingConfig.bases.replace(SequencingConfig.no_call_base, "")
