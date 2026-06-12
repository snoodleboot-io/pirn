"""``SDTMDomainValidator`` — validate SDTM domain conformance.

Production version cross-checks records against the CDISC SDTM IG
(Standard Data Tabulation Model Implementation Guide) for the chosen
domain (e.g., ``AE``, ``DM``, ``EX``). This stub asserts that every
required field on every record is populated and returns a single
boolean verdict.

Algorithm:
    1. Validate domain and required_fields.
    2. For each record, check that every required field is non-empty.
    3. Return True if all records pass, False otherwise.

Math:
    Validity predicate:

    $$\\text{valid} = \\bigwedge_{r \\in R} \\bigwedge_{f \\in F} r.f \\neq \\emptyset$$

    where $F$ is the set of required fields.

References:
    - CDISC. (2022). Study Data Tabulation Model Implementation Guide v3.4.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class SDTMDomainValidator(Knot):
    """Validate SDTM-domain field completeness across trial records."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalTrialRecord],
        domain: Knot | str,
        required_fields: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            domain=domain,
            required_fields=required_fields,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        domain: str,
        required_fields: Sequence[str],
        **_: Any,
    ) -> bool:
        """Check that every required SDTM field is populated on every record.

        Args:
            records: Sequence of ClinicalTrialRecord objects to validate.
            domain: Non-empty SDTM domain code (e.g. 'AE', 'DM').
            required_fields: Non-empty sequence of required field names.

        Returns:
            True if every required field on every record is non-empty, False otherwise.

        Raises:
            ValueError: If domain is empty or required_fields is empty.
            TypeError: If required_fields is not a list or tuple.
        """
        if not isinstance(domain, str) or not domain:
            raise ValueError("SDTMDomainValidator: domain must be a non-empty string")
        if not isinstance(required_fields, (list, tuple)):
            raise TypeError("SDTMDomainValidator: required_fields must be a list or tuple")
        if len(required_fields) == 0:
            raise ValueError("SDTMDomainValidator: required_fields must be non-empty")
        for field_name in required_fields:
            if not isinstance(field_name, str) or not field_name:
                raise ValueError(
                    "SDTMDomainValidator: every required_field must be a non-empty string"
                )
        for record in records:
            for field_name in required_fields:
                value = getattr(record, field_name, None)
                if value in (None, "", 0, ()):
                    return False
        return True
