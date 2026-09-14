"""``EncounterTimelineAssembler`` — chronologically order encounters by patient.

Returns a mapping ``patient_id -> tuple[ClinicalRecord, ...]`` sorted
by ``observed_at`` ascending. Stable across equal timestamps.

Algorithm:
    1. Receive a sequence of ClinicalRecords.
    2. Validate that records is a list/tuple and every element is a ClinicalRecord.
    3. Group records by patient_id into a dict of lists.
    4. Sort each list by observed_at ascending.
    5. Return the dict as a Mapping of patient_id to sorted ClinicalRecord tuples.


References:
    - HL7 FHIR R4 Encounter: https://hl7.org/fhir/R4/encounter.html
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_record import ClinicalRecord


class EncounterTimelineAssembler(Knot):
    """Group :class:`ClinicalRecord`s by patient and sort by time."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalRecord],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self,
        records: Sequence[ClinicalRecord],
        **_: Any,
    ) -> Mapping[str, tuple[ClinicalRecord, ...]]:
        """Group records by patient_id, sort each group by observed_at, and return the timeline map.

        Args:
            records: Sequence of ClinicalRecords to assemble into a timeline.

        Returns:
            A mapping from patient_id to a tuple of ClinicalRecords sorted by observed_at ascending.

        Raises:
            TypeError: If records is not a list/tuple or contains non-ClinicalRecord items.
        """
        if not isinstance(records, (list, tuple)):
            raise TypeError("EncounterTimelineAssembler: records must be list/tuple")
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError("EncounterTimelineAssembler: every record must be a ClinicalRecord")
        grouped: dict[str, list[ClinicalRecord]] = {}
        for record in records:
            grouped.setdefault(record.patient_id, []).append(record)
        return {
            patient_id: tuple(sorted(items, key=lambda r: r.observed_at))
            for patient_id, items in grouped.items()
        }
