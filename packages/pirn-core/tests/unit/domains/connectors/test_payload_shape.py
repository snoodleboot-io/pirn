"""Unit tests for :class:`PayloadShape`."""

from __future__ import annotations

import unittest
from types import MappingProxyType

import numpy as np

from pirn.connectors.payload_shape import PayloadShape


class TestMappingGuards(unittest.TestCase):
    def test_is_mapping_accepts_any_mapping(self) -> None:
        # Arrange
        values: list[object] = [{"a": 1}, {1: "a"}, MappingProxyType({"a": 1})]

        # Act / Assert
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(PayloadShape.is_mapping(value))

    def test_is_mapping_rejects_non_mapping(self) -> None:
        for value in ([("a", 1)], None, "a"):
            with self.subTest(value=value):
                self.assertFalse(PayloadShape.is_mapping(value))

    def test_is_str_mapping_accepts_any_mapping(self) -> None:
        self.assertTrue(PayloadShape.is_str_mapping({"a": 1}))
        self.assertTrue(PayloadShape.is_str_mapping(MappingProxyType({"a": 1})))

    def test_is_str_mapping_rejects_non_mapping(self) -> None:
        self.assertFalse(PayloadShape.is_str_mapping([("a", 1)]))
        self.assertFalse(PayloadShape.is_str_mapping(None))


class TestDictGuards(unittest.TestCase):
    def test_is_dict_accepts_only_dict(self) -> None:
        self.assertTrue(PayloadShape.is_dict({1: 2}))
        self.assertFalse(PayloadShape.is_dict(MappingProxyType({"a": 1})))

    def test_is_str_dict_accepts_only_dict(self) -> None:
        self.assertTrue(PayloadShape.is_str_dict({"a": 1}))
        self.assertFalse(PayloadShape.is_str_dict(MappingProxyType({"a": 1})))
        self.assertFalse(PayloadShape.is_str_dict([("a", 1)]))


class TestSequenceGuards(unittest.TestCase):
    def test_is_list_distinguishes_list_from_tuple(self) -> None:
        self.assertTrue(PayloadShape.is_list([1]))
        self.assertFalse(PayloadShape.is_list((1,)))

    def test_is_tuple_distinguishes_tuple_from_list(self) -> None:
        self.assertTrue(PayloadShape.is_tuple((1, 2)))
        self.assertFalse(PayloadShape.is_tuple([1, 2]))

    def test_is_sequence_accepts_list_and_tuple_only(self) -> None:
        self.assertTrue(PayloadShape.is_sequence([1]))
        self.assertTrue(PayloadShape.is_sequence((1,)))
        self.assertFalse(PayloadShape.is_sequence("ab"))
        self.assertFalse(PayloadShape.is_sequence({1}))

    def test_is_iterable_accepts_any_iterable(self) -> None:
        for value in ([1], (1,), {1}, "ab", iter([1])):
            with self.subTest(value=value):
                self.assertTrue(PayloadShape.is_iterable(value))
        self.assertFalse(PayloadShape.is_iterable(1))


class TestNdarrayGuard(unittest.TestCase):
    def test_is_ndarray_accepts_numpy_array(self) -> None:
        self.assertTrue(PayloadShape.is_ndarray(np.zeros((2,))))
        self.assertTrue(PayloadShape.is_ndarray(np.array(1.0)))

    def test_is_ndarray_rejects_array_likes(self) -> None:
        self.assertFalse(PayloadShape.is_ndarray([1.0, 2.0]))
        self.assertFalse(PayloadShape.is_ndarray(np.float64(1.0)))


class TestRows(unittest.TestCase):
    def test_falsy_value_yields_no_rows(self) -> None:
        for value in (None, [], ()):
            with self.subTest(value=value):
                self.assertEqual(PayloadShape.rows(value, source="X"), [])

    def test_list_of_mappings_is_materialised_in_order(self) -> None:
        # Arrange
        records = [{"id": 1}, {"id": 2}]

        # Act
        rows = PayloadShape.rows(records, source="X")

        # Assert
        self.assertEqual(rows, records)
        self.assertIsNot(rows, records)

    def test_tuple_of_mappings_is_accepted(self) -> None:
        self.assertEqual(PayloadShape.rows(({"id": 1},), source="X"), [{"id": 1}])

    def test_non_collection_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "X: expected a list of records; got str"):
            PayloadShape.rows("records", source="X")

    def test_non_mapping_element_raises(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "X: expected every record to be a mapping; got int"
        ):
            PayloadShape.rows([{"id": 1}, 2], source="X")


class TestEntities(unittest.TestCase):
    def test_returns_mapping_elements_in_order(self) -> None:
        # Act
        rows = PayloadShape.entities([{"id": 1}, {"id": 2}])

        # Assert
        self.assertEqual(rows, [{"id": 1}, {"id": 2}])

    def test_skips_non_mapping_elements(self) -> None:
        rows = PayloadShape.entities([{"id": 1}, "junk", 3, None])

        self.assertEqual(rows, [{"id": 1}])

    def test_non_list_yields_no_rows(self) -> None:
        for value in (None, {"id": 1}, ({"id": 1},)):
            with self.subTest(value=value):
                self.assertEqual(PayloadShape.entities(value), [])
