"""Tests for :class:`ValueShape`."""

from __future__ import annotations

import unittest

from pirn_data.value_shape import ValueShape


class TestValueShape(unittest.TestCase):
    def test_is_mapping(self) -> None:
        assert ValueShape.is_mapping({"a": 1})
        assert not ValueShape.is_mapping([("a", 1)])

    def test_is_str_mapping(self) -> None:
        assert ValueShape.is_str_mapping({"a": 1})
        assert not ValueShape.is_str_mapping("a")

    def test_is_sequence(self) -> None:
        assert ValueShape.is_sequence([1, 2])
        assert ValueShape.is_sequence("ab")
        assert not ValueShape.is_sequence({1, 2})

    def test_is_tuple(self) -> None:
        assert ValueShape.is_tuple((1,))
        assert not ValueShape.is_tuple([1])

    def test_is_list(self) -> None:
        assert ValueShape.is_list([1])
        assert not ValueShape.is_list((1,))

    def test_is_list_or_tuple(self) -> None:
        assert ValueShape.is_list_or_tuple([1])
        assert ValueShape.is_list_or_tuple((1,))
        assert not ValueShape.is_list_or_tuple("1")

    def test_is_iterable(self) -> None:
        assert ValueShape.is_iterable(iter([1]))
        assert ValueShape.is_iterable({1})
        assert not ValueShape.is_iterable(1)

    def test_is_callable(self) -> None:
        assert ValueShape.is_callable(len)
        assert ValueShape.is_callable(lambda: None)
        assert not ValueShape.is_callable("len")
