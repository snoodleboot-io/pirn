"""``PHIRedactor`` — return a copy of a :class:`ClinicalRecord` with PHI removed.

Patient ids and encounter ids are replaced with stable opaque tokens so
downstream linkage (cohort, OMOP) still works, while the source-system
tag is preserved unchanged. A real implementation would also walk free-
text fields with a Safe-Harbor rule set.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class PHIRedactor(Knot):
    """Return a redacted copy of a :class:`ClinicalRecord`."""

    def __init__(
        self,
        *,
        record: ClinicalRecord,
        salt: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(record, ClinicalRecord):
            raise TypeError("PHIRedactor: record must be a ClinicalRecord")
        if not isinstance(salt, str):
            raise TypeError("PHIRedactor: salt must be a string")
        if not salt:
            raise ValueError("PHIRedactor: salt must be non-empty")
        self._record = record
        self._salt = salt
        super().__init__(_config=_config, **kwargs)

    def _hash_id(self, value: str) -> str:
        digest = hashlib.sha256(
            f"{self._salt}|{value}".encode("utf-8")
        ).hexdigest()
        return digest[:16]

    async def process(self, **_: Any) -> ClinicalRecord:
        record = self._record
        return ClinicalRecord(
            patient_id=self._hash_id(record.patient_id),
            encounter_id=self._hash_id(record.encounter_id),
            observation_codes=record.observation_codes,
            observed_at=record.observed_at,
            source_system=record.source_system,
        )
