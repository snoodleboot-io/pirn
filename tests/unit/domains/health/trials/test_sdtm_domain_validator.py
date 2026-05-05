"""Unit tests for :class:`SDTMDomainValidator`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.sdtm_domain_validator import SDTMDomainValidator
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry


def _record(
    trial_id: str = "T-1",
    subject_id: str = "S-1",
    visit_number: int = 1,
) -> ClinicalTrialRecord:
    return ClinicalTrialRecord(
        trial_id=trial_id,
        subject_id=subject_id,
        visit_number=visit_number,
        observation_codes=("AE001",),
        observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


@knot
async def emit_records() -> Sequence[ClinicalTrialRecord]:
    return (_record(), _record(subject_id="S-2"))


@knot
async def emit_records_with_blanks() -> Sequence[ClinicalTrialRecord]:
    return (_record(), ClinicalTrialRecord())


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_records(self) -> None:
        with self.assertRaisesRegex(TypeError, "records"):
            SDTMDomainValidator(
                records="not-a-knot",  # type: ignore[arg-type]
                domain="AE",
                required_fields=("trial_id",),
                _config=KnotConfig(id="v"),
            )

    def test_rejects_empty_domain(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "domain"):
                SDTMDomainValidator(
                    records=r,
                    domain="",
                    required_fields=("trial_id",),
                    _config=KnotConfig(id="v"),
                )

    def test_rejects_empty_required_fields(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "required_fields"):
                SDTMDomainValidator(
                    records=r,
                    domain="AE",
                    required_fields=(),
                    _config=KnotConfig(id="v"),
                )

    def test_rejects_non_sequence_required_fields(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "required_fields"):
                SDTMDomainValidator(
                    records=r,
                    domain="AE",
                    required_fields=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="v"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_when_all_fields_populated(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            SDTMDomainValidator(
                records=r,
                domain="AE",
                required_fields=("trial_id", "subject_id"),
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["v"] is True

    async def test_returns_false_when_any_field_blank(self) -> None:
        with Tapestry() as t:
            r = emit_records_with_blanks(_config=KnotConfig(id="r"))
            SDTMDomainValidator(
                records=r,
                domain="AE",
                required_fields=("trial_id", "subject_id"),
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["v"] is False
