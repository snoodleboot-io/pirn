"""Unit tests for :class:`PVTTable`."""

from __future__ import annotations
import unittest

from pirn.domains.oilgas.types.pvt_table import PVTTable


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        pvt = PVTTable()
        assert pvt.fluid_id == ""
        assert pvt.pressure_count == 0
        assert pvt.temperature_count == 0

    def test_full_values(self) -> None:
        pvt = PVTTable(fluid_id="fluid-1", pressure_count=10, temperature_count=5)
        assert pvt.fluid_id == "fluid-1"
        assert pvt.pressure_count == 10
        assert pvt.temperature_count == 5


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_round_trip(self) -> None:
        pvt = PVTTable(fluid_id="f", pressure_count=2, temperature_count=3)
        assert pvt._pirn_audit_dict() == {
            "fluid_id": "f",
            "pressure_count": 2,
            "temperature_count": 3,
        }


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        pvt = PVTTable(fluid_id="f")
        try:
            pvt.fluid_id = "g"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("PVTTable must be frozen")
