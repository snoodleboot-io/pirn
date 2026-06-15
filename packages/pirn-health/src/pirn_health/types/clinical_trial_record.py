"""``ClinicalTrialRecord`` — visit-level clinical trial observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ClinicalTrialRecord(PirnOpaqueValue):
    """Subject observation at a specific trial visit."""

    trial_id: str = ""
    subject_id: str = ""
    visit_number: int = 0
    observation_codes: tuple[str, ...] = ()
    observed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "subject_id": self.subject_id,
            "visit_number": self.visit_number,
            "observation_codes": list(self.observation_codes),
            "observed_at": self.observed_at.isoformat(),
        }
