"""``ClinicalTrialEligibilityFilter`` — predicate-based subject filter.

Each criterion maps to a callable predicate ``(record) -> bool``. A
record passes only when every predicate returns ``True``. Production
deployments swap the predicates for criterion DSL evaluation.

Algorithm:
    1. Receive a sequence of ClinicalRecords and a criteria mapping.
    2. Validate types of records and each predicate in the mapping.
    3. For each record, evaluate every predicate.
    4. Keep records for which all predicates return True.
    5. Return the passing records as a tuple.


References:
    - CDISC CDASH: https://www.cdisc.org/standards/foundational/cdash
    - HL7 FHIR R4 ResearchSubject: https://hl7.org/fhir/R4/researchsubject.html
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class ClinicalTrialEligibilityFilter(Knot):
    """Keep only :class:`ClinicalRecord`s satisfying every predicate."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalRecord],
        criteria: Knot | Mapping[str, Callable[[ClinicalRecord], bool]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            criteria=criteria,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[ClinicalRecord],
        criteria: Mapping[str, Callable[[ClinicalRecord], bool]],
        **_: Any,
    ) -> tuple[ClinicalRecord, ...]:
        """Apply all eligibility predicates to each record and return only those that pass every criterion.

        Args:
            records: Sequence of ClinicalRecords to filter.
            criteria: Mapping of criterion name to callable predicate.

        Returns:
            A tuple of ClinicalRecords that satisfy every configured eligibility criterion.

        Raises:
            TypeError: If records or criteria have wrong types.
        """
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "ClinicalTrialEligibilityFilter: records must be list/tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "ClinicalTrialEligibilityFilter: every record must be a ClinicalRecord"
                )
        if not isinstance(criteria, Mapping):
            raise TypeError(
                "ClinicalTrialEligibilityFilter: criteria must be a Mapping"
            )
        for name, predicate in criteria.items():
            if not callable(predicate):
                raise TypeError(
                    f"ClinicalTrialEligibilityFilter: criterion {name!r} must be callable"
                )
        return tuple(
            record
            for record in records
            if all(predicate(record) for predicate in criteria.values())
        )
