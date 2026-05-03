"""``RWECohortExtractor`` — extract a real-world evidence cohort from structured EHR/claims data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RWECohortExtractor(Knot):
    """Extract a real-world evidence cohort from structured EHR/claims data."""

    def __init__(
        self,
        *,
        patient_data: Knot,
        inclusion_criteria: dict[str, Any],
        exclusion_criteria: dict[str, Any],
        index_date_col: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(patient_data, Knot):
            raise TypeError("RWECohortExtractor: patient_data must be a Knot")
        if not isinstance(inclusion_criteria, dict):
            raise TypeError(
                "RWECohortExtractor: inclusion_criteria must be a dict"
            )
        if not isinstance(exclusion_criteria, dict):
            raise TypeError(
                "RWECohortExtractor: exclusion_criteria must be a dict"
            )
        if not isinstance(index_date_col, str) or not index_date_col:
            raise ValueError(
                "RWECohortExtractor: index_date_col must be a non-empty string"
            )
        self._inclusion_criteria = inclusion_criteria
        self._exclusion_criteria = exclusion_criteria
        self._index_date_col = index_date_col
        super().__init__(patient_data=patient_data, _config=_config, **kwargs)

    @staticmethod
    def _matches_criteria(record: dict[str, Any], criteria: dict[str, Any]) -> bool:
        for field, value in criteria.items():
            if record.get(field) != value:
                return False
        return True

    async def process(
        self,
        patient_data: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Extract cohort by applying inclusion and exclusion criteria to patient records.

        Args:
            patient_data: List of patient row dicts from EHR or claims data.

        Returns:
            Dict with cohort (list of included patient dicts), n_included (int),
            n_excluded (int), and exclusion_reasons (dict mapping reason label to count).
        """
        cohort: list[dict[str, Any]] = []
        n_excluded = 0
        exclusion_reasons: dict[str, int] = {}

        for record in patient_data:
            if self._inclusion_criteria and not self._matches_criteria(record, self._inclusion_criteria):
                n_excluded += 1
                reason = "failed_inclusion"
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
                continue
            if self._exclusion_criteria and self._matches_criteria(record, self._exclusion_criteria):
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
