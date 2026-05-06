"""``RWECohortExtractor`` — extract a real-world evidence cohort from structured EHR/claims data.

Algorithm:
    1. Validate inclusion_criteria, exclusion_criteria, and index_date_col.
    2. Apply inclusion criteria; records not matching are excluded.
    3. Apply exclusion criteria; records matching are excluded.
    4. Return the surviving cohort with exclusion statistics.

Math:
    Inclusion predicate for record *r* and criteria *C*:

    $$P_I(r) = \\bigwedge_{(f, v) \\in C} r[f] = v$$

    Exclusion predicate:

    $$P_E(r) = \\bigvee_{(f, v) \\in C_E} r[f] = v$$

References:
    - Schneeweiss, S., et al. (2019). Using routinely collected EHR data for pharmacoepidemiology. Epidemiology.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RWECohortExtractor(Knot):
    """Extract a real-world evidence cohort from structured EHR/claims data."""

    def __init__(
        self,
        *,
        patient_data: Knot | list[dict[str, Any]],
        inclusion_criteria: Knot | dict[str, Any],
        exclusion_criteria: Knot | dict[str, Any],
        index_date_col: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            patient_data=patient_data,
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
            index_date_col=index_date_col,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _matches_criteria(record: dict[str, Any], criteria: dict[str, Any]) -> bool:
        for field, value in criteria.items():
            if record.get(field) != value:
                return False
        return True

    async def process(
        self,
        patient_data: list[dict[str, Any]],
        inclusion_criteria: dict[str, Any],
        exclusion_criteria: dict[str, Any],
        index_date_col: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Extract cohort by applying inclusion and exclusion criteria to patient records.

        Args:
            patient_data: List of patient row dicts from EHR or claims data.
            inclusion_criteria: Dict of field-value pairs that must match.
            exclusion_criteria: Dict of field-value pairs that must not match.
            index_date_col: Non-empty column name for the index date.

        Returns:
            Dict with cohort (list of included patient dicts), n_included (int),
            n_excluded (int), and exclusion_reasons (dict mapping reason label to count).

        Raises:
            TypeError: If inclusion/exclusion criteria are not dicts.
            ValueError: If index_date_col is empty.
        """
        if not isinstance(inclusion_criteria, dict):
            raise TypeError("RWECohortExtractor: inclusion_criteria must be a dict")
        if not isinstance(exclusion_criteria, dict):
            raise TypeError("RWECohortExtractor: exclusion_criteria must be a dict")
        if not isinstance(index_date_col, str) or not index_date_col:
            raise ValueError("RWECohortExtractor: index_date_col must be a non-empty string")
        cohort: list[dict[str, Any]] = []
        n_excluded = 0
        exclusion_reasons: dict[str, int] = {}

        for record in patient_data:
            if inclusion_criteria and not self._matches_criteria(record, inclusion_criteria):
                n_excluded += 1
                reason = "failed_inclusion"
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
                continue
            if exclusion_criteria and self._matches_criteria(record, exclusion_criteria):
                n_excluded += 1
                reason = "met_exclusion"
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
                continue
            cohort.append(record)

        return {
            "cohort": cohort,
            "n_included": len(cohort),
            "n_excluded": n_excluded,
            "exclusion_reasons": exclusion_reasons,
        }
