"""Unit tests for :class:`ClinicalTrialRecord`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.content_hasher import ContentHasher

from pirn_health.types.clinical_trial_record import ClinicalTrialRecord


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        r = ClinicalTrialRecord()
        assert r.trial_id == ""
        assert r.subject_id == ""
        assert r.visit_number == 0
        assert r.observation_codes == ()

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
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
        when = datetime(2026, 1, 1, tzinfo=UTC)
        r = ClinicalTrialRecord(
            trial_id="T1",
            subject_id="S1",
            visit_number=2,
            observation_codes=("A", "B"),
            observed_at=when,
        )
        d = r._pirn_audit_dict()
        assert d["trial_id"] == "T1"
        assert d["visit_number"] == 2
        assert d["observation_codes"] == ["A", "B"]
        assert d["observed_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))

    def test_audit_dict_never_carries_the_raw_subject_id(self) -> None:
        r = ClinicalTrialRecord(trial_id="T1", subject_id="SUBJ-0012", visit_number=2)

        d = r._pirn_audit_dict()

        assert "subject_id" not in d
        assert "SUBJ-0012" not in repr(d)
        assert d["subject_id_hash"] == ContentHasher.hash("SUBJ-0012")

    def test_two_subjects_stay_distinguishable_in_lineage(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        first = ClinicalTrialRecord(trial_id="T1", subject_id="SUBJ-0012", observed_at=when)
        second = ClinicalTrialRecord(trial_id="T1", subject_id="SUBJ-0013", observed_at=when)

        assert first._pirn_audit_dict() != second._pirn_audit_dict()
        assert ContentHasher.hash(first) != ContentHasher.hash(second)


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        r = ClinicalTrialRecord()
        try:
            r.trial_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ClinicalTrialRecord must be frozen")
