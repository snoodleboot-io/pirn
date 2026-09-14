"""Unit tests for :class:`PayloadShape`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.connectors.payload_shape import PayloadShape


class TestIterableGuard(unittest.TestCase):
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
            ValueError, "X: expected every record to be a mapping with only string keys; got int"
        ):
            PayloadShape.rows([{"id": 1}, 2], source="X")

    def test_mapping_with_a_non_string_key_raises(self) -> None:
        # The old guard never inspected keys, so {1: "a"} passed as Mapping[str, ...].
        with self.assertRaisesRegex(ValueError, "only string keys; got dict"):
            PayloadShape.rows([{"id": 1}, {1: "a"}], source="X")

    def test_malformed_row_is_never_dropped(self) -> None:
        # The deleted lenient extractor skipped non-mapping rows and returned the rest.
        with self.assertRaises(ValueError):
            PayloadShape.rows([{"id": 1}, "junk", None], source="X")
