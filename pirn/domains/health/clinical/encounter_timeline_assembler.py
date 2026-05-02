"""``EncounterTimelineAssembler`` — chronologically order encounters by patient.

Returns a mapping ``patient_id -> tuple[ClinicalRecord, ...]`` sorted
by ``observed_at`` ascending. Stable across equal timestamps.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class EncounterTimelineAssembler(Knot):
    """Group :class:`ClinicalRecord`s by patient and sort by time."""

    def __init__(
        self,
        *,
        records: Sequence[ClinicalRecord],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "EncounterTimelineAssembler: records must be list/tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "EncounterTimelineAssembler: every record must be a ClinicalRecord"
                )
        self._records = tuple(records)
        super().__init__(_config=_config, **kwargs)

    async def process(
        self, **_: Any
    ) -> Mapping[str, tuple[ClinicalRecord, ...]]:
        grouped: dict[str, list[ClinicalRecord]] = {}
        for record in self._records:
            grouped.setdefault(record.patient_id, []).append(record)
        return {
            patient_id: tuple(sorted(items, key=lambda r: r.observed_at))
            for patient_id, items in grouped.items()
        }
