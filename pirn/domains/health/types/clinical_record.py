"""``ClinicalRecord`` — a single clinical observation snapshot.

Frozen dataclass shared across the clinical sub-area; carries the small
identifier set every downstream knot (PHI redaction, OMOP mapping, ICD
validation, NLP extraction) needs without dragging vendor SDK types
through the pipeline.
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
        return {
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "observation_codes": list(self.observation_codes),
            "observed_at": self.observed_at.isoformat(),
            "source_system": self.source_system,
        }
