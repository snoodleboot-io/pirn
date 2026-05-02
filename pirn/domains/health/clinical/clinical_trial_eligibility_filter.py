"""``ClinicalTrialEligibilityFilter`` — predicate-based subject filter.

Each criterion maps to a callable predicate ``(record) -> bool``. A
record passes only when every predicate returns ``True``. Production
deployments swap the predicates for criterion DSL evaluation.
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
        records: Sequence[ClinicalRecord],
        criteria: Mapping[str, Callable[[ClinicalRecord], bool]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._records = tuple(records)
        self._criteria = dict(criteria)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[ClinicalRecord, ...]:
        return tuple(
            record
            for record in self._records
            if all(predicate(record) for predicate in self._criteria.values())
        )
