"""``PHIRedactor`` — return a copy of a :class:`ClinicalRecord` with PHI removed.

Patient ids and encounter ids are replaced with stable opaque tokens so
downstream linkage (cohort, OMOP) still works, while the source-system
tag is preserved unchanged. A real implementation would also walk free-
text fields with a Safe-Harbor rule set.

Algorithm:
    1. Receive a ClinicalRecord and a salt string.
    2. Validate that record is a ClinicalRecord and salt is a non-empty string.
    3. Hash patient_id and encounter_id with SHA-256 keyed by salt.
    4. Truncate each digest to 16 hex characters for a compact stable token.
    5. Return a new ClinicalRecord with the hashed identifiers.

Math:
    $$\\text{token}(v) = \\text{SHA-256}(\\text{salt} \\| v)[:16]$$

References:
    - HIPAA Safe Harbor: https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/
    - SHA-256: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf
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
        record: Knot | ClinicalRecord,
        salt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(record=record, salt=salt, _config=_config, **kwargs)

    async def process(
        self,
        record: ClinicalRecord,
        salt: str,
        **_: Any,
    ) -> ClinicalRecord:
        """Hash patient_id and encounter_id with the configured salt and return a redacted ClinicalRecord.

        Args:
            record: The ClinicalRecord whose PHI fields should be redacted.
            salt: Non-empty string used as a HMAC-style prefix for stable hashing.

        Returns:
            A ClinicalRecord with patient_id and encounter_id replaced by stable opaque hash tokens.

        Raises:
            TypeError: If record is not a ClinicalRecord or salt is not a string.
            ValueError: If salt is empty.
        """
        if not isinstance(record, ClinicalRecord):
            raise TypeError("PHIRedactor: record must be a ClinicalRecord")
        if not isinstance(salt, str):
            raise TypeError("PHIRedactor: salt must be a string")
        if not salt:
            raise ValueError("PHIRedactor: salt must be non-empty")

        def _hash_id(value: str) -> str:
            digest = hashlib.sha256(
                f"{salt}|{value}".encode()
            ).hexdigest()
            return digest[:16]

        return ClinicalRecord(
            patient_id=_hash_id(record.patient_id),
            encounter_id=_hash_id(record.encounter_id),
            observation_codes=record.observation_codes,
            observed_at=record.observed_at,
            source_system=record.source_system,
        )
