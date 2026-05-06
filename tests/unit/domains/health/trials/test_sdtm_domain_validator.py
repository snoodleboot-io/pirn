"""Unit tests for :class:`SDTMDomainValidator`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.core.knot_config import KnotConfig
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


_RECORDS = (_record(), _record(subject_id="S-2"))
_RECORDS_WITH_BLANKS = (_record(), ClinicalTrialRecord())


def _make_knot(domain: str = "AE") -> SDTMDomainValidator:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("rec", tuple, default=_RECORDS, _config=KnotConfig(id="rec"))
        return SDTMDomainValidator(
            records=src,
            domain=domain,
            required_fields=("trial_id",),
            _config=KnotConfig(id="v"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_domain(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "domain"):
            await knot.process(
                records=_RECORDS,
                domain="",
                required_fields=("trial_id",),
            )

    async def test_rejects_empty_required_fields(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "required_fields"):
            await knot.process(
                records=_RECORDS,
                domain="AE",
                required_fields=(),
            )

    async def test_rejects_non_sequence_required_fields(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "required_fields"):
            await knot.process(
                records=_RECORDS,
                domain="AE",
                required_fields=42,  # type: ignore[arg-type]
            )

    async def test_returns_true_when_all_fields_populated(self) -> None:
        knot = _make_knot()
        result = await knot.process(
            records=_RECORDS,
            domain="AE",
            required_fields=("trial_id", "subject_id"),
        )
        assert result is True

    async def test_returns_false_when_any_field_blank(self) -> None:
        knot = _make_knot()
        result = await knot.process(
            records=_RECORDS_WITH_BLANKS,
            domain="AE",
            required_fields=("trial_id", "subject_id"),
        )
        assert result is False
