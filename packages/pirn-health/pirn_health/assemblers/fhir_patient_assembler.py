"""``FhirPatientAssembler`` — assemble :class:`ClinicalRecord` objects from FHIR dicts.

Sits between a connector that materialises FHIR Patient JSON bundles (as
``list[dict]``) and downstream domain knots that consume
:class:`~pirn_health.types.clinical_record.ClinicalRecord`.

Algorithm:
    1. Receive a non-empty ``records`` list of FHIR-shaped dicts.
    2. Validate that ``records`` is a non-empty ``list``.
    3. Parse each dict into a :class:`ClinicalRecord`, extracting known FHIR fields.
    4. Return the records as a ``tuple[ClinicalRecord, ...]``.

References:
    - HL7 FHIR R4 Patient: https://hl7.org/fhir/R4/patient.html
    - fhirclient: https://github.com/smart-on-fhir/client-py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_record import ClinicalRecord


def _parse_record(raw: dict[str, Any]) -> ClinicalRecord:
    observed_at_raw = raw.get("observed_at") or raw.get("recordedDate", "")
    if observed_at_raw:
        try:
            observed_at = datetime.fromisoformat(observed_at_raw)
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            observed_at = datetime(1970, 1, 1, tzinfo=UTC)
    else:
        observed_at = datetime(1970, 1, 1, tzinfo=UTC)
    codes_raw = raw.get("observation_codes", raw.get("code", []))
    if isinstance(codes_raw, str):
        codes_raw = [codes_raw]
    observation_codes = tuple(str(c) for c in codes_raw if c)
    return ClinicalRecord(
        patient_id=str(raw.get("patient_id", raw.get("id", ""))),
        encounter_id=str(raw.get("encounter_id", raw.get("encounterId", ""))),
        observation_codes=observation_codes,
        observed_at=observed_at,
        source_system=str(raw.get("source_system", "fhir")),
    )


class FhirPatientAssembler(Assembler):
    """Assemble a tuple of :class:`ClinicalRecord` objects from FHIR Patient dicts."""

    def __init__(
        self,
        *,
        records: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self,
        records: list[dict[str, Any]],
        **_: Any,
    ) -> tuple[ClinicalRecord, ...]:
        """Parse FHIR Patient dicts into :class:`ClinicalRecord` objects.

        Args:
            records: Non-empty list of FHIR-shaped patient dicts, already materialised
                by an upstream connector knot.

        Returns:
            Tuple of :class:`ClinicalRecord` objects, one per input dict.

        Raises:
            TypeError: If ``records`` is not a ``list``.
            ValueError: If ``records`` is empty.
        """
        if not isinstance(records, list):
            raise TypeError(
                f"FhirPatientAssembler: records must be a list, got {type(records).__name__}"
            )
        if not records:
            raise ValueError("FhirPatientAssembler: records must be non-empty")
        return tuple(_parse_record(r) for r in records)
