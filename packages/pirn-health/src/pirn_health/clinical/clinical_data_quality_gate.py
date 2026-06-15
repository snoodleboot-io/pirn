"""``ClinicalDataQualityCheck`` — fail-loud check against missingness.

A simple completeness check: the fraction of non-empty
``observation_codes`` tuples must be above ``min_completeness``. Real
deployments would also check ranges, types, cross-record consistency,
and referential integrity against vocabularies.

Algorithm:
    1. Receive a sequence of ClinicalRecords and a min_completeness threshold.
    2. Validate that min_completeness is numeric and in [0, 1].
    3. Count records with non-empty observation_codes.
    4. Compute completeness = non_empty / total (1.0 when empty input).
    5. Raise ClinicalDataQualityError when completeness < min_completeness.
    6. Return the records tuple when completeness meets the threshold.

Math:
    $$\\text{completeness} = \\frac{|\\{r : r.\\text{observation\\_codes} \\neq ()\\}|}{|\\text{records}|}$$

References:
    - HL7 FHIR R4 Observation resource: https://hl7.org/fhir/R4/observation.html
    - LOINC: https://loinc.org/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.clinical.clinical_data_quality_error import (
    ClinicalDataQualityError,
)
from pirn_health.types.clinical_record import ClinicalRecord


class ClinicalDataQualityCheck(Knot):
    """Pass through records iff completeness exceeds threshold."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalRecord],
        min_completeness: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            min_completeness=min_completeness,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[ClinicalRecord],
        min_completeness: float,
        **_: Any,
    ) -> tuple[ClinicalRecord, ...]:
        """Check completeness of observation_codes across records and raise if below threshold.

        Args:
            records: Sequence of ClinicalRecords to quality-check.
            min_completeness: Fraction in [0, 1]; records must meet or exceed this.

        Returns:
            The tuple of ClinicalRecords when completeness meets the threshold.

        Raises:
            TypeError: If records is not a list/tuple or contains non-ClinicalRecord items.
            TypeError: If min_completeness is not numeric.
            ValueError: If min_completeness is outside [0, 1].
            ClinicalDataQualityError: If the fraction of records with non-empty
                observation_codes is below min_completeness.
        """
        if not isinstance(records, (list, tuple)):
            raise TypeError("ClinicalDataQualityGate: records must be list/tuple")
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError("ClinicalDataQualityGate: every record must be a ClinicalRecord")
        if not isinstance(min_completeness, (int, float)):
            raise TypeError("ClinicalDataQualityGate: min_completeness must be numeric")
        if not 0.0 <= float(min_completeness) <= 1.0:
            raise ValueError("ClinicalDataQualityGate: min_completeness must be in [0, 1]")
        records_tuple = tuple(records)
        if not records_tuple:
            completeness = 1.0
        else:
            non_empty = sum(1 for r in records_tuple if r.observation_codes)
            completeness = non_empty / len(records_tuple)
        if completeness < float(min_completeness):
            raise ClinicalDataQualityError(
                f"completeness {completeness:.3f} below threshold {float(min_completeness):.3f}"
            )
        return records_tuple


# Backwards-compatibility alias (old name kept so existing imports do not break).
ClinicalDataQualityGate = ClinicalDataQualityCheck
