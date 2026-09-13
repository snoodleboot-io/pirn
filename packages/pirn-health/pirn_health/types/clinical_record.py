"""``ClinicalRecord`` — a single clinical observation snapshot.

Frozen dataclass shared across the clinical sub-area; carries the small
identifier set every downstream knot (PHI redaction, OMOP mapping, ICD
validation, NLP extraction) needs without dragging vendor SDK types
through the pipeline.

PHI safety:
    ``patient_id`` and ``encounter_id`` are excluded from
    :meth:`_pirn_audit_dict`. Callers that construct a ``ClinicalRecord``
    before it passes through :class:`~pirn_health.clinical.phi_redactor.PHIRedactor`
    (or an assembler that hashes at construction time, e.g.
    :class:`~pirn_health.assemblers.fhir_patient_assembler.FhirPatientAssembler`)
    may still be holding a raw identifier in those fields; the audit trail
    must never assume they are already sanitised.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ClinicalRecord(PirnOpaqueValue):
    """Patient observation tied to an encounter."""

    patient_id: str = ""
    encounter_id: str = ""
    observation_codes: tuple[str, ...] = ()
    observed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)
    source_system: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        # patient_id / encounter_id are deliberately excluded: this record may
        # carry a raw identifier at any point before PHIRedactor (or an
        # assembler that hashes at construction time) runs, and the audit
        # trail must never risk emitting PHI.
        return {
            "observation_codes": list(self.observation_codes),
            "observed_at": self.observed_at.isoformat(),
            "source_system": self.source_system,
        }
