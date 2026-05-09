"""``FastqQualityController`` — FASTQ quality-control summary.

Parses FASTQ records using the stdlib and computes mean Phred quality score
from the quality string (ASCII - 33 encoding).

Algorithm:
    1. Receive fastq_path and sample_id strings.
    2. Validate that both are non-empty strings.
    3. Parse FASTQ records (4-line groups: header, seq, +, qual).
    4. Compute mean Phred quality score across all bases in all reads.
    5. Return a GenomicsRecord carrying quality_score and sample metadata.


References:
    - FastQC: https://www.bioinformatics.babraham.ac.uk/projects/fastqc/
    - Andrews (2010) FastQC: a quality control tool for high throughput sequence data.
    - Cock et al. (2010) The Sanger FASTQ file format for sequences with quality scores. NAR.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.genomics_record import GenomicsRecord


def _mean_phred(fastq_path: str) -> float:
    total: float = 0.0
    count: int = 0
    try:
        with open(fastq_path, encoding="ascii", errors="replace") as fh:
            while True:
                header = fh.readline()
                if not header:
                    break
                fh.readline()  # sequence
                fh.readline()  # +
                qual = fh.readline().rstrip("\n")
                for ch in qual:
                    total += ord(ch) - 33
                    count += 1
    except OSError:
        return 0.0
    return total / count if count > 0 else 0.0


class FastqQualityController(Knot):
    """Compute QC metrics for one FASTQ file."""

    def __init__(
        self,
        *,
        fastq_path: Knot | str,
        sample_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fastq_path=fastq_path,
            sample_id=sample_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fastq_path: str,
        sample_id: str,
        **_: Any,
    ) -> GenomicsRecord:
        """Compute QC metrics from the FASTQ file and return a GenomicsRecord summary.

        Args:
            fastq_path: Non-empty path to the input FASTQ file.
            sample_id: Non-empty sample identifier string.

        Returns:
            GenomicsRecord carrying the sample_id and mean Phred quality_score.

        Raises:
            TypeError: If fastq_path or sample_id is not a string.
            ValueError: If fastq_path or sample_id is empty.
        """
        if not isinstance(fastq_path, str):
            raise TypeError("FastqQualityController: fastq_path must be a string")
        if not fastq_path:
            raise ValueError("FastqQualityController: fastq_path must be non-empty")
        if not isinstance(sample_id, str):
            raise TypeError("FastqQualityController: sample_id must be a string")
        if not sample_id:
            raise ValueError("FastqQualityController: sample_id must be non-empty")
        quality_score = await asyncio.to_thread(_mean_phred, fastq_path)
        return GenomicsRecord(
            sample_id=sample_id,
            locus="",
            genotype="",
            quality_score=quality_score,
        )
