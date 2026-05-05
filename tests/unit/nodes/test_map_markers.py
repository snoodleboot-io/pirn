"""Unit tests for map marker types (Map, ZipMap, DictMap)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import DictMap, Map, MapTypeError, ZipMap
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ListSource(Source):
    async def process(self, **_: Any) -> list:
        return [1, 2, 3]


class TestMapConstruction(unittest.TestCase):
    def test_map_stores_source(self) -> None:
        with Tapestry():
            src = _ListSource(_config=KnotConfig(id="src"))
            m = Map(src)
        self.assertIs(m.source, src)

    def test_zip_map_stores_source(self) -> None:
        with Tapestry():
            src = _ListSource(_config=KnotConfig(id="src"))
            zm = ZipMap(src)
        self.assertIs(zm.source, src)

    def test_dict_map_stores_source(self) -> None:
        with Tapestry():
            src = _ListSource(_config=KnotConfig(id="src"))
            dm = DictMap(src)
        self.assertIs(dm.source, src)


class TestMapTypeError(unittest.TestCase):
    def test_map_type_error_is_type_error(self) -> None:
        self.assertTrue(issubclass(MapTypeError, TypeError))

    def test_map_type_error_instantiates(self) -> None:
        err = MapTypeError("bad type")
        self.assertIn("bad type", str(err))


class TestMapDistinctTypes(unittest.TestCase):
    def test_map_zip_dict_are_distinct(self) -> None:
        with Tapestry():
            src = _ListSource(_config=KnotConfig(id="src"))
            self.assertNotIsInstance(Map(src), ZipMap)
            self.assertNotIsInstance(ZipMap(src), DictMap)
            self.assertNotIsInstance(DictMap(src), Map)
