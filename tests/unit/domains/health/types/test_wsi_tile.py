"""Unit tests for :class:`WSITile`."""

from __future__ import annotations
import unittest

from pirn.domains.health.types.wsi_tile import WSITile


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        t = WSITile()
        assert t.slide_id == ""
        assert t.tile_x == 0
        assert t.tile_y == 0
        assert t.level == 0
        assert t.width == 0
        assert t.height == 0

    def test_full(self) -> None:
        t = WSITile(
            slide_id="slide-1",
            tile_x=100,
            tile_y=200,
            level=2,
            width=512,
            height=512,
        )
        assert t.slide_id == "slide-1"
        assert t.tile_x == 100
        assert t.tile_y == 200
        assert t.level == 2
        assert t.width == 512
        assert t.height == 512


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        t = WSITile(
            slide_id="slide-1",
            tile_x=100,
            tile_y=200,
            level=2,
            width=512,
            height=512,
        )
        d = t._pirn_audit_dict()
        assert d["slide_id"] == "slide-1"
        assert d["tile_x"] == 100
        assert d["tile_y"] == 200
        assert d["level"] == 2
        assert d["width"] == 512
        assert d["height"] == 512
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        t = WSITile()
        try:
            t.slide_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("WSITile must be frozen")
