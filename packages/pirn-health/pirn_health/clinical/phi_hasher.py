"""``PhiHasher`` — shared salted SHA-256 hashing for PHI identifier fields.

:class:`~pirn_health.clinical.phi_redactor.PHIRedactor` and
:class:`~pirn_health.assemblers.fhir_patient_assembler.FhirPatientAssembler`
both need to turn a raw identifier (``patient_id``, ``encounter_id``) into a
stable opaque token. This class is the single implementation both call, so
the two sites cannot silently diverge into two different hashing schemes.

Algorithm:
    1. Concatenate salt and value as ``f"{salt}|{value}"``.
    2. Compute the SHA-256 digest of the UTF-8 encoding.
    3. Truncate the hex digest to 16 characters for a compact stable token.

Math:
    $$\\text{token}(v) = \\text{SHA-256}(\\text{salt} \\| v)[:16]$$

References:
    - HIPAA Safe Harbor: https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/
    - SHA-256: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf
"""

from __future__ import annotations

import hashlib


class PhiHasher:
    """Shared salted SHA-256 hashing for PHI identifier fields."""

    @staticmethod
    def hash_identifier(salt: str, value: str) -> str:
        """Return a stable 16-character opaque token for ``value`` under ``salt``."""
        digest = hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()
        return digest[:16]
