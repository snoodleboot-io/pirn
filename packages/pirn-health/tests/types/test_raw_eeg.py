"""Unit tests for :class:`RawEEG`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.content_hasher import ContentHasher

from pirn_health.types.raw_eeg import RawEEG


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        r = RawEEG()
        assert r.subject_id == ""
        assert r.channel_count == 0
        assert r.sample_rate_hz == 0.0
        assert r.duration_sec == 0.0

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        r = RawEEG(
            subject_id="S1",
            channel_count=64,
            sample_rate_hz=1000.0,
            duration_sec=120.0,
            fetched_at=when,
        )
        assert r.subject_id == "S1"
        assert r.channel_count == 64
        assert r.sample_rate_hz == 1000.0
        assert r.duration_sec == 120.0
        assert r.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        r = RawEEG(
            subject_id="S1",
            channel_count=64,
            sample_rate_hz=1000.0,
            duration_sec=120.0,
            fetched_at=when,
        )
        d = r._pirn_audit_dict()
        assert d["channel_count"] == 64
        assert d["sample_rate_hz"] == 1000.0
        assert d["duration_sec"] == 120.0
        assert d["fetched_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))

    def test_audit_dict_never_carries_the_raw_subject_id(self) -> None:
        r = RawEEG(subject_id="MRN-4471", channel_count=64, sample_rate_hz=1000.0)

        d = r._pirn_audit_dict()

        assert "subject_id" not in d
        assert "MRN-4471" not in repr(d)
        assert d["subject_id_hash"] == ContentHasher.hash("MRN-4471")

    def test_two_subjects_stay_distinguishable_in_lineage(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        first = RawEEG(subject_id="MRN-4471", channel_count=64, fetched_at=when)
        second = RawEEG(subject_id="MRN-9902", channel_count=64, fetched_at=when)

        assert first._pirn_audit_dict() != second._pirn_audit_dict()
        assert ContentHasher.hash(first) != ContentHasher.hash(second)


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        r = RawEEG()
        try:
            r.subject_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("RawEEG must be frozen")
