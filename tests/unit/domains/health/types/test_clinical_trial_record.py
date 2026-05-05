"""Unit tests for :class:`ClinicalTrialRecord`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        r = ClinicalTrialRecord()
        assert r.trial_id == ""
        assert r.subject_id == ""
        assert r.visit_number == 0
        assert r.observation_codes == ()

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r = ClinicalTrialRecord(
            trial_id="T1",
            subject_id="S1",
            visit_number=2,
            observation_codes=("A", "B"),
            observed_at=when,
        )
        assert r.trial_id == "T1"
        assert r.subject_id == "S1"
        assert r.visit_number == 2
        assert r.observation_codes == ("A", "B")
        assert r.observed_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r = ClinicalTrialRecord(
            trial_id="T1",
            subject_id="S1",
            visit_number=2,
            observation_codes=("A", "B"),
            observed_at=when,
        )
        d = r._pirn_audit_dict()
        assert d["trial_id"] == "T1"
        assert d["subject_id"] == "S1"
        assert d["visit_number"] == 2
        assert d["observation_codes"] == ["A", "B"]
        assert d["observed_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        r = ClinicalTrialRecord()
        try:
            r.trial_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ClinicalTrialRecord must be frozen")
