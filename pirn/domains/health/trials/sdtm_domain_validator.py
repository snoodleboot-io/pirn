"""``SDTMDomainValidator`` — validate SDTM domain conformance.

Production version cross-checks records against the CDISC SDTM IG
(Standard Data Tabulation Model Implementation Guide) for the chosen
domain (e.g., ``AE``, ``DM``, ``EX``). This stub asserts that every
required field on every record is populated and returns a single
boolean verdict.
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
        records: Knot,
        domain: str,
        required_fields: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, Knot):
            raise TypeError("SDTMDomainValidator: records must be a Knot")
        if not isinstance(domain, str) or not domain:
            raise ValueError(
                "SDTMDomainValidator: domain must be a non-empty string"
            )
        if not isinstance(required_fields, (list, tuple)):
            raise TypeError(
                "SDTMDomainValidator: required_fields must be a list or tuple"
            )
        if len(required_fields) == 0:
            raise ValueError(
                "SDTMDomainValidator: required_fields must be non-empty"
            )
        for field_name in required_fields:
            if not isinstance(field_name, str) or not field_name:
                raise ValueError(
                    "SDTMDomainValidator: every required_field must be a non-empty string"
                )
        self._domain = domain
        self._required_fields = tuple(required_fields)
        super().__init__(records=records, _config=_config, **kwargs)

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def required_fields(self) -> tuple[str, ...]:
        return self._required_fields

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        **_: Any,
    ) -> bool:
        for record in records:
            for field_name in self._required_fields:
                value = getattr(record, field_name, None)
                if value in (None, "", 0, ()):
                    return False
        return True
