"""Unit tests for :class:`SegyVolume`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.oilgas.types.segy_volume import SegyVolume


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        vol = SegyVolume()
        assert vol.volume_id == ""
        assert vol.inline_count == 0
        assert vol.xline_count == 0
        assert vol.sample_count == 0
        assert isinstance(vol.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vol = SegyVolume(
            volume_id="vol-1",
            inline_count=10,
            xline_count=20,
            sample_count=30,
            fetched_at=when,
        )
        assert vol.volume_id == "vol-1"
        assert vol.inline_count == 10
        assert vol.xline_count == 20
        assert vol.sample_count == 30
        assert vol.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_keys(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vol = SegyVolume(volume_id="v", inline_count=1, fetched_at=when)
        d = vol._pirn_audit_dict()
        assert d["volume_id"] == "v"
        assert d["inline_count"] == 1
        assert d["xline_count"] == 0
        assert d["sample_count"] == 0
        assert d["fetched_at"] == when.isoformat()


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        vol = SegyVolume(volume_id="v")
        try:
            vol.volume_id = "x"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SegyVolume must be frozen")
