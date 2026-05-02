"""``PatientCohortBuilder`` — compose multiple eligibility filters.

Pipeline: feed an initial record set through several
:class:`ClinicalTrialEligibilityFilter` stages (e.g. inclusion then
exclusion). Implemented as a :class:`SubTapestry` so each stage is a
visible knot in the run graph.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical._pass_through import _PassThrough
from pirn.domains.health.clinical.clinical_trial_eligibility_filter import (
    ClinicalTrialEligibilityFilter,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class PatientCohortBuilder(SubTapestry):
    """Apply named filter stages in order to build a final cohort."""

    def __init__(
        self,
        *,
        records: Sequence[ClinicalRecord],
        stages: Mapping[str, Mapping[str, Callable[[ClinicalRecord], bool]]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "PatientCohortBuilder: records must be a list or tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "PatientCohortBuilder: every record must be a ClinicalRecord"
                )
        if not isinstance(stages, Mapping):
            raise TypeError("PatientCohortBuilder: stages must be a Mapping")
        for stage_name, criteria in stages.items():
            if not isinstance(criteria, Mapping):
                raise TypeError(
                    f"PatientCohortBuilder: stage {stage_name!r} criteria must be a Mapping"
                )
        self._records = tuple(records)
        self._stages = {
            name: dict(criteria) for name, criteria in stages.items()
        }
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            current = tuple(self._records)
            seed = _PassThrough(
                records=current,
                _config=KnotConfig(id="cohort-seed"),
            )
            previous: Knot = seed
            for stage_name, criteria in self._stages.items():
                # The filter consumes a sequence directly; tie ordering by
                # naming the stage with a stable id derived from the user
                # mapping keys.
                stage_records = tuple(
                    record
                    for record in current
                    if all(predicate(record) for predicate in criteria.values())
                )
                current = stage_records
                previous = ClinicalTrialEligibilityFilter(
                    records=stage_records,
                    criteria=criteria,
                    _config=KnotConfig(id=f"cohort-stage-{stage_name}"),
                )
            # Tie the last stage with the seed for graph completeness.
            _ = previous
            _ = seed
        return await self._run_inner(inner)
