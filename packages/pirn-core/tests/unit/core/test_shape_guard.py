"""Tests for :class:`ShapeGuard`."""

from __future__ import annotations

import unittest
from collections import OrderedDict
from types import MappingProxyType

from pirn.core.shape_guard import ShapeGuard


class TestShapeGuardDicts(unittest.TestCase):
    def test_is_dict_accepts_any_dict(self) -> None:
        self.assertTrue(ShapeGuard.is_dict({1: "a"}))
        self.assertTrue(ShapeGuard.is_dict(OrderedDict()))

    def test_is_dict_rejects_non_dicts(self) -> None:
        for value in ([], (), "x", None, MappingProxyType({})):
            with self.subTest(value=value):
                self.assertFalse(ShapeGuard.is_dict(value))

    def test_is_str_keyed_dict_requires_every_key_to_be_a_string(self) -> None:
        self.assertTrue(ShapeGuard.is_str_keyed_dict({"a": 1, "b": [2]}))
        self.assertTrue(ShapeGuard.is_str_keyed_dict({}))
        self.assertFalse(ShapeGuard.is_str_keyed_dict({"a": 1, 2: "b"}))
        self.assertFalse(ShapeGuard.is_str_keyed_dict(["a"]))


class TestShapeGuardMappings(unittest.TestCase):
    def test_is_mapping_accepts_non_dict_mappings(self) -> None:
        self.assertTrue(ShapeGuard.is_mapping(MappingProxyType({"a": 1})))
        self.assertFalse(ShapeGuard.is_mapping([("a", 1)]))

    def test_is_str_keyed_mapping_requires_every_key_to_be_a_string(self) -> None:
        self.assertTrue(ShapeGuard.is_str_keyed_mapping(MappingProxyType({"a": 1})))
        self.assertFalse(ShapeGuard.is_str_keyed_mapping(MappingProxyType({1: "a"})))
        self.assertFalse(ShapeGuard.is_str_keyed_mapping("ab"))


class TestShapeGuardSequences(unittest.TestCase):
    def test_is_list(self) -> None:
        self.assertTrue(ShapeGuard.is_list([1, "a"]))
        self.assertFalse(ShapeGuard.is_list((1,)))

    def test_is_tuple(self) -> None:
        self.assertTrue(ShapeGuard.is_tuple((1, "a")))
        self.assertFalse(ShapeGuard.is_tuple([1]))
