"""Unit tests for :class:`WellPath3D`."""

from __future__ import annotations

from datetime import datetime, timezone

from pirn.domains.oilgas.types.well_path_3d import WellPath3D


class TestConstruction:
    def test_default_values(self) -> None:
        path = WellPath3D()
        assert path.well_id == ""
        assert path.point_count == 0
        assert isinstance(path.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        path = WellPath3D(well_id="W1", point_count=128, fetched_at=when)
        assert path.well_id == "W1"
        assert path.point_count == 128
        assert path.fetched_at == when


class TestAuditDict:
    def test_audit_dict_iso_timestamp(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        path = WellPath3D(well_id="W1", point_count=5, fetched_at=when)
        d = path._pirn_audit_dict()
        assert d == {
            "well_id": "W1",
            "point_count": 5,
            "fetched_at": when.isoformat(),
        }


class TestFrozen:
    def test_frozen_disallows_mutation(self) -> None:
        path = WellPath3D(well_id="W1")
        try:
            path.point_count = 99  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("WellPath3D must be frozen")
