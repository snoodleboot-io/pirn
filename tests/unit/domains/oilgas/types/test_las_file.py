"""Unit tests for :class:`LASFile`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.oilgas.types.las_file import LASFile


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        las = LASFile()
        assert las.well_id == ""
        assert las.curves == ()
        assert las.depth_unit == "m"
        assert isinstance(las.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        las = LASFile(
            well_id="well-A",
            curves=("GR", "RHOB"),
            depth_unit="ft",
            fetched_at=when,
        )
        assert las.well_id == "well-A"
        assert las.curves == ("GR", "RHOB")
        assert las.depth_unit == "ft"
        assert las.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_curves_as_list(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        las = LASFile(
            well_id="well-A", curves=("GR",), depth_unit="m", fetched_at=when
        )
        d = las._pirn_audit_dict()
        assert d["well_id"] == "well-A"
        assert d["curves"] == ["GR"]
        assert d["depth_unit"] == "m"
        assert d["fetched_at"] == when.isoformat()


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        las = LASFile(well_id="A")
        try:
            las.well_id = "B"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("LASFile must be frozen")
