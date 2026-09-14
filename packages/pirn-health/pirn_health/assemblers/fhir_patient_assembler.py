"""``FhirPatientAssembler`` — assemble :class:`ClinicalRecord` objects from FHIR dicts.

Sits between a connector that materialises FHIR Patient JSON bundles (as
``list[dict]``) and downstream domain knots that consume
:class:`~pirn_health.types.clinical_record.ClinicalRecord`.

Algorithm:
    1. Receive a non-empty ``records`` list of FHIR-shaped dicts and a ``salt`` string.
    2. Validate that ``records`` is a non-empty ``list`` and ``salt`` is a non-empty string.
    3. Parse each dict into field values, extracting known FHIR fields.
    4. Hash ``patient_id`` and ``encounter_id`` with the same salted SHA-256 scheme as
       :class:`~pirn_health.clinical.phi_redactor.PHIRedactor` (via ``PhiHasher``) so no
       raw identifier ever reaches a :class:`ClinicalRecord`.
    5. Return the records as a ``tuple[ClinicalRecord, ...]``.

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

from pirn_health.clinical.phi_hasher import (
    PhiHasher,
)
from pirn_health.types.clinical_record import ClinicalRecord


class FhirPatientAssembler(Assembler):
    """Assemble a tuple of sanitised :class:`ClinicalRecord` objects from FHIR Patient dicts."""

    def __init__(
        self,
        *,
        records: Knot,
        salt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, salt=salt, _config=_config, **kwargs)

    async def process(
        self,
        records: list[dict[str, Any]],
        salt: str,
        **_: Any,
    ) -> tuple[ClinicalRecord, ...]:
        """Parse FHIR Patient dicts into sanitised :class:`ClinicalRecord` objects.

        Args:
            records: Non-empty list of FHIR-shaped patient dicts, already materialised
                by an upstream connector knot.
            salt: Non-empty string used to hash ``patient_id`` and ``encounter_id``.

        Returns:
            Tuple of :class:`ClinicalRecord` objects, one per input dict, with
            ``patient_id``/``encounter_id`` replaced by stable opaque hash tokens.

        Raises:
            TypeError: If ``records`` is not a ``list`` or ``salt`` is not a ``str``.
            ValueError: If ``records`` is empty or ``salt`` is empty.
        """
        if not isinstance(records, list):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError(
                f"FhirPatientAssembler: records must be a list, got {type(records).__name__}"
            )
        if not records:
            raise ValueError("FhirPatientAssembler: records must be non-empty")
        if not isinstance(salt, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError("FhirPatientAssembler: salt must be a string")
        if not salt:
            raise ValueError("FhirPatientAssembler: salt must be non-empty")
        return tuple(self._parse_record(r, salt) for r in records)

    @staticmethod
    def _parse_record(raw: dict[str, Any], salt: str) -> ClinicalRecord:
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
        raw_patient_id = str(raw.get("patient_id", raw.get("id", "")))
        raw_encounter_id = str(raw.get("encounter_id", raw.get("encounterId", "")))
        return ClinicalRecord(
            patient_id=PhiHasher.hash_identifier(salt, raw_patient_id),
            encounter_id=PhiHasher.hash_identifier(salt, raw_encounter_id),
            observation_codes=observation_codes,
            observed_at=observed_at,
            source_system=str(raw.get("source_system", "fhir")),
        )
