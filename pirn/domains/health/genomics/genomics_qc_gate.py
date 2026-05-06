"""``GenomicsQCCheck`` — gate the pipeline by QC metrics.

Production version computes mean coverage, mapping rate, contamination
estimates, etc. This stub gates on a minimum quality_score across the
:class:`GenomicsRecord` summaries it receives.

Algorithm:
    1. Receive records sequence of GenomicsRecord and min_quality threshold.
    2. Validate records is a list/tuple of GenomicsRecord and min_quality is numeric.
    3. Iterate over records and compare each quality_score to min_quality.
    4. Raise GenomicsQCError for any record failing the threshold.
    5. Return the full tuple of records when all pass.


References:
    - ENCODE quality metrics: https://www.encodeproject.org/data-standards/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.genomics_qc_error import GenomicsQCError
from pirn.domains.health.types.genomics_record import GenomicsRecord


class GenomicsQCCheck(Knot):
    """Pass through records iff every quality_score >= threshold."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[GenomicsRecord],
        min_quality: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            min_quality=min_quality,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[GenomicsRecord],
        min_quality: float,
        **_: Any,
    ) -> tuple[GenomicsRecord, ...]:
        """Check every record's quality_score against the minimum threshold and raise GenomicsQCError if any fail.

        Args:
            records: List or tuple of GenomicsRecord objects to check.
            min_quality: Minimum acceptable quality_score (numeric).

        Returns:
            Tuple of all records when every quality_score meets the threshold.

        Raises:
            TypeError: If records is not list/tuple or contains non-GenomicsRecord, or min_quality is not numeric.
            GenomicsQCError: If any record's quality_score is below min_quality.
        """
        if not isinstance(records, (list, tuple)):
            raise TypeError("GenomicsQCCheck: records must be a list or tuple")
        for record in records:
            if not isinstance(record, GenomicsRecord):
                raise TypeError("GenomicsQCCheck: every record must be a GenomicsRecord")
        if not isinstance(min_quality, (int, float)):
            raise TypeError("GenomicsQCCheck: min_quality must be numeric")
        threshold = float(min_quality)
        for record in records:
            if record.quality_score < threshold:
                raise GenomicsQCError(
                    f"sample {record.sample_id!r} quality "
                    f"{record.quality_score} below {threshold}"
                )
        return tuple(records)


# Backward-compatibility alias.
GenomicsQCGate = GenomicsQCCheck
