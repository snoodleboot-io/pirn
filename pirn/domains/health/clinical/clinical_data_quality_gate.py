"""``ClinicalDataQualityGate`` — fail-loud gate against missingness.

A simple completeness check: the fraction of non-empty
``observation_codes`` tuples must be above ``min_completeness``. Real
deployments would also check ranges, types, cross-record consistency,
and referential integrity against vocabularies.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.clinical_data_quality_error import (
    ClinicalDataQualityError,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord


class ClinicalDataQualityGate(Knot):
    """Pass through records iff completeness exceeds threshold."""

    def __init__(
        self,
        *,
        records: Sequence[ClinicalRecord],
        min_completeness: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "ClinicalDataQualityGate: records must be list/tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "ClinicalDataQualityGate: every record must be a ClinicalRecord"
                )
        if not isinstance(min_completeness, (int, float)):
            raise TypeError(
                "ClinicalDataQualityGate: min_completeness must be numeric"
            )
        if not 0.0 <= float(min_completeness) <= 1.0:
            raise ValueError(
                "ClinicalDataQualityGate: min_completeness must be in [0, 1]"
            )
        self._records = tuple(records)
        self._min_completeness = float(min_completeness)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[ClinicalRecord, ...]:
        if not self._records:
            completeness = 1.0
        else:
            non_empty = sum(
                1 for r in self._records if r.observation_codes
            )
            completeness = non_empty / len(self._records)
        if completeness < self._min_completeness:
            raise ClinicalDataQualityError(
                f"completeness {completeness:.3f} below threshold "
                f"{self._min_completeness:.3f}"
            )
        return self._records
