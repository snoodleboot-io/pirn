"""Unit tests for :class:`DrillingParameters`."""

from __future__ import annotations

from datetime import datetime, timezone

from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters


class TestConstruction:
    def test_default_values(self) -> None:
        params = DrillingParameters()
        assert params.well_id == ""
        assert params.depth_count == 0
        assert isinstance(params.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        params = DrillingParameters(well_id="W", depth_count=4, fetched_at=when)
        assert params.well_id == "W"
        assert params.depth_count == 4
        assert params.fetched_at == when


class TestAuditDict:
    def test_audit_dict_keys(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        params = DrillingParameters(well_id="W", depth_count=2, fetched_at=when)
        d = params._pirn_audit_dict()
        assert d == {
            "well_id": "W",
            "depth_count": 2,
            "fetched_at": when.isoformat(),
        }


class TestFrozen:
    def test_frozen_disallows_mutation(self) -> None:
        params = DrillingParameters(well_id="W")
        try:
            params.depth_count = 1  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DrillingParameters must be frozen")
