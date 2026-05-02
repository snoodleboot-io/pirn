"""Unit tests for :class:`ClinicalRecord`."""

from __future__ import annotations

from datetime import datetime, timezone

from pirn.domains.health.types.clinical_record import ClinicalRecord


class TestConstruction:
    def test_default_construction(self) -> None:
        record = ClinicalRecord()
        assert record.patient_id == ""
        assert record.encounter_id == ""
        assert record.observation_codes == ()
        assert record.source_system == ""

    def test_full_construction(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = ClinicalRecord(
            patient_id="P1",
            encounter_id="E1",
            observation_codes=("A", "B"),
            observed_at=when,
            source_system="epic",
        )
        assert record.patient_id == "P1"
        assert record.encounter_id == "E1"
        assert record.observation_codes == ("A", "B")
        assert record.observed_at == when
        assert record.source_system == "epic"


class TestAuditDict:
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = ClinicalRecord(
            patient_id="P1",
            encounter_id="E1",
            observation_codes=("A", "B"),
            observed_at=when,
            source_system="epic",
        )
        d = record._pirn_audit_dict()
        assert d["patient_id"] == "P1"
        assert d["encounter_id"] == "E1"
        assert d["observation_codes"] == ["A", "B"]
        assert d["observed_at"] == when.isoformat()
        assert d["source_system"] == "epic"
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen:
    def test_frozen_disallows_mutation(self) -> None:
        record = ClinicalRecord()
        try:
            record.patient_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ClinicalRecord must be frozen")
