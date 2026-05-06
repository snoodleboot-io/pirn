"""``FastqQualityController`` — FASTQ quality-control summary.

Production version would parse FASTQ files via ``pyfaidx`` /
``pysam.FastxFile`` and emit per-read quality metrics. This stub
returns a deterministic summary :class:`GenomicsRecord`.

Algorithm:
    1. Receive fastq_path and sample_id strings.
    2. Validate that both are non-empty strings.
    3. Parse FASTQ records and compute per-base quality statistics.
    4. Summarise mean quality score, GC content, and adapter contamination.
    5. Return a GenomicsRecord carrying quality_score and sample metadata.


References:
    - FastQC: https://www.bioinformatics.babraham.ac.uk/projects/fastqc/
    - Andrews (2010) FastQC: a quality control tool for high throughput sequence data.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.genomics_record import GenomicsRecord


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
            GenomicsRecord carrying the sample_id and zero-valued quality metrics.

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
        return GenomicsRecord(
            sample_id=sample_id,
            locus="",
            genotype="",
            quality_score=0.0,
        )
