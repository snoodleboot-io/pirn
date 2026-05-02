"""Unit tests for :class:`RawEEG`."""

from __future__ import annotations

from datetime import datetime, timezone

from pirn.domains.health.types.raw_eeg import RawEEG


class TestConstruction:
    def test_default(self) -> None:
        r = RawEEG()
        assert r.subject_id == ""
        assert r.channel_count == 0
        assert r.sample_rate_hz == 0.0
        assert r.duration_sec == 0.0

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
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


class TestAuditDict:
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r = RawEEG(
            subject_id="S1",
            channel_count=64,
            sample_rate_hz=1000.0,
            duration_sec=120.0,
            fetched_at=when,
        )
        d = r._pirn_audit_dict()
        assert d["subject_id"] == "S1"
        assert d["channel_count"] == 64
        assert d["sample_rate_hz"] == 1000.0
        assert d["duration_sec"] == 120.0
        assert d["fetched_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen:
    def test_frozen_disallows_mutation(self) -> None:
        r = RawEEG()
        try:
            r.subject_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("RawEEG must be frozen")
