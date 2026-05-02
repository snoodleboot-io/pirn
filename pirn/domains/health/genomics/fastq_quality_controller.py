"""``FastqQualityController`` — FASTQ quality-control summary.

Production version would parse FASTQ files via ``pyfaidx`` /
``pysam.FastxFile`` and emit per-read quality metrics. This stub
records the requested file path and yields a deterministic summary
:class:`GenomicsRecord`.
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
        fastq_path: str,
        sample_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(fastq_path, str):
            raise TypeError(
                "FastqQualityController: fastq_path must be a string"
            )
        if not fastq_path:
            raise ValueError(
                "FastqQualityController: fastq_path must be non-empty"
            )
        if not isinstance(sample_id, str):
            raise TypeError(
                "FastqQualityController: sample_id must be a string"
            )
        if not sample_id:
            raise ValueError(
                "FastqQualityController: sample_id must be non-empty"
            )
        self._fastq_path = fastq_path
        self._sample_id = sample_id
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> GenomicsRecord:
        return GenomicsRecord(
            sample_id=self._sample_id,
            locus="",
            genotype="",
            quality_score=0.0,
        )
