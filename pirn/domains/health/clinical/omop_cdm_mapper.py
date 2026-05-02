"""``OMOPCDMMapper`` — map a :class:`ClinicalRecord` to OMOP CDM rows.

Production version would resolve source codes against the OMOP
vocabulary tables (``concept``, ``concept_relationship``) and emit one
row per OMOP target table (``person``, ``visit_occurrence``,
``observation``, ...). The stub returns a single dict shaped like an
OMOP ``observation`` row so downstream sinks can be wired.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class OMOPCDMMapper(Knot):
    """Map a :class:`ClinicalRecord` to an OMOP CDM row tuple."""

    def __init__(
        self,
        *,
        record: ClinicalRecord,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(record, ClinicalRecord):
            raise TypeError(
                "OMOPCDMMapper: record must be a ClinicalRecord"
            )
        self._record = record
        super().__init__(_config=_config, **kwargs)

    async def process(
        self, **_: Any
    ) -> tuple[Mapping[str, Any], ...]:
        record = self._record
        row: Mapping[str, Any] = {
            "person_id": record.patient_id,
            "visit_occurrence_id": record.encounter_id,
            "observation_concept_id": 0,
            "observation_date": record.observed_at.isoformat(),
            "observation_source_value": "|".join(record.observation_codes),
        }
        return (row,)
