"""``OMOPCDMMapper`` — map a :class:`ClinicalRecord` to OMOP CDM rows.

Production version would resolve source codes against the OMOP
vocabulary tables (``concept``, ``concept_relationship``) and emit one
row per OMOP target table (``person``, ``visit_occurrence``,
``observation``, ...). The stub returns a single dict shaped like an
OMOP ``observation`` row so downstream sinks can be wired.

Algorithm:
    1. Receive a ClinicalRecord.
    2. Validate that record is a ClinicalRecord.
    3. Resolve observation codes against OMOP concept vocabulary.
    4. Construct OMOP CDM row dict from the record fields.
    5. Return the rows as a tuple.


References:
    - OMOP CDM: https://ohdsi.github.io/CommonDataModel/
    - OHDSI: https://www.ohdsi.org/
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_record import ClinicalRecord


class OMOPCDMMapper(Knot):
    """Map a :class:`ClinicalRecord` to an OMOP CDM row tuple."""

    def __init__(
        self,
        *,
        record: Knot | ClinicalRecord,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(record=record, _config=_config, **kwargs)

    async def process(
        self,
        record: ClinicalRecord,
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Map the ClinicalRecord to an OMOP observation row tuple.

        Args:
            record: The ClinicalRecord to map to OMOP CDM format.

        Returns:
            A tuple containing a single OMOP observation row dict derived from the configured ClinicalRecord.

        Raises:
            TypeError: If record is not a ClinicalRecord.
        """
        if not isinstance(record, ClinicalRecord):
            raise TypeError("OMOPCDMMapper: record must be a ClinicalRecord")
        row: Mapping[str, Any] = {
            "person_id": record.patient_id,
            "visit_occurrence_id": record.encounter_id,
            "observation_concept_id": 0,
            "observation_date": record.observed_at.isoformat(),
            "observation_source_value": "|".join(record.observation_codes),
        }
        return (row,)
