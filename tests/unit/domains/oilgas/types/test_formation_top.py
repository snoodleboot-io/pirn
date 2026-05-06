"""Unit tests for :class:`FormationTop`."""

from __future__ import annotations

import unittest

from pirn.domains.oilgas.types.formation_top import FormationTop


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        top = FormationTop()
        assert top.well_id == ""
        assert top.formation_name == ""
        assert top.depth_md == 0.0

    def test_full_values(self) -> None:
        top = FormationTop(well_id="W", formation_name="Niobrara", depth_md=2500.0)
        assert top.well_id == "W"
        assert top.formation_name == "Niobrara"
        assert top.depth_md == 2500.0


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_round_trip(self) -> None:
        top = FormationTop(well_id="W", formation_name="N", depth_md=100.5)
        assert top._pirn_audit_dict() == {
            "well_id": "W",
            "formation_name": "N",
            "depth_md": 100.5,
        }


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        top = FormationTop(well_id="W")
        try:
            top.depth_md = 9.0  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("FormationTop must be frozen")
