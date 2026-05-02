"""``GenomicsQCGate`` — gate the pipeline by QC metrics.

Production version computes mean coverage, mapping rate, contamination
estimates, etc. This stub gates on a minimum quality_score across the
:class:`GenomicsRecord` summaries it receives.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.genomics_record import GenomicsRecord


class GenomicsQCError(ValueError):
    """Raised when genomics QC metrics fall below threshold."""


class GenomicsQCGate(Knot):
    """Pass through records iff every quality_score >= threshold."""

    def __init__(
        self,
        *,
        records: Sequence[GenomicsRecord],
        min_quality: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "GenomicsQCGate: records must be a list or tuple"
            )
        for record in records:
            if not isinstance(record, GenomicsRecord):
                raise TypeError(
                    "GenomicsQCGate: every record must be a GenomicsRecord"
                )
        if not isinstance(min_quality, (int, float)):
            raise TypeError("GenomicsQCGate: min_quality must be numeric")
        self._records = tuple(records)
        self._min_quality = float(min_quality)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[GenomicsRecord, ...]:
        for record in self._records:
            if record.quality_score < self._min_quality:
                raise GenomicsQCError(
                    f"sample {record.sample_id!r} quality "
                    f"{record.quality_score} below {self._min_quality}"
                )
        return self._records
