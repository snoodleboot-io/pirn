"""Unit tests for :class:`SignalFrame`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.health.types.signal_frame import SignalFrame


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        s = SignalFrame()
        assert s.signal_id == ""
        assert s.channel_count == 0
        assert s.sample_rate_hz == 0.0
        assert s.samples_per_channel == 0

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s = SignalFrame(
            signal_id="sig",
            channel_count=8,
            sample_rate_hz=250.0,
            samples_per_channel=1024,
            fetched_at=when,
        )
        assert s.signal_id == "sig"
        assert s.channel_count == 8
        assert s.sample_rate_hz == 250.0
        assert s.samples_per_channel == 1024
        assert s.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s = SignalFrame(
            signal_id="sig",
            channel_count=8,
            sample_rate_hz=250.0,
            samples_per_channel=1024,
            fetched_at=when,
        )
        d = s._pirn_audit_dict()
        assert d["signal_id"] == "sig"
        assert d["channel_count"] == 8
        assert d["sample_rate_hz"] == 250.0
        assert d["samples_per_channel"] == 1024
        assert d["fetched_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        s = SignalFrame()
        try:
            s.signal_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SignalFrame must be frozen")
