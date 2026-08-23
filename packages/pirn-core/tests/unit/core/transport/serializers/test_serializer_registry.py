"""Unit tests for :class:`SerializerRegistry`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.transport.serializers.numpy_serializer import NumpySerializer
from pirn.core.transport.serializers.pickle_serializer import PickleSerializer
from pirn.core.transport.serializers.serializer_registry import SerializerRegistry


class TestSerializerRegistry(unittest.TestCase):
    def test_default_registry_routes_ndarray_to_numpy(self) -> None:
        registry = SerializerRegistry.default()
        arr = np.array([1.0, 2.0])
        ser = registry.get(arr)
        assert isinstance(ser, NumpySerializer)

    def test_default_registry_routes_dict_to_pickle(self) -> None:
        registry = SerializerRegistry.default()
        ser = registry.get({"key": "value"})
        assert isinstance(ser, PickleSerializer)

    def test_custom_registration_takes_priority(self) -> None:
        registry = SerializerRegistry()
        custom = PickleSerializer()
        registry.register(dict, custom)
        assert registry.get({"a": 1}) is custom

    def test_later_registration_wins_for_same_type(self) -> None:
        registry = SerializerRegistry()
        first = PickleSerializer()
        second = PickleSerializer()
        registry.register(dict, first)
        registry.register(dict, second)
        assert registry.get({"a": 1}) is second

    def test_subclass_inherits_parent_registration(self) -> None:
        class MyDict(dict):
            pass

        registry = SerializerRegistry()
        ser = PickleSerializer()
        registry.register(dict, ser)
        assert registry.get(MyDict()) is ser

    def test_fallback_to_pickle_for_unknown_type(self) -> None:
        registry = SerializerRegistry()

        class Exotic:
            pass

        ser = registry.get(Exotic())
        assert isinstance(ser, PickleSerializer)

    def test_get_by_type_name_matches_numpy(self) -> None:
        registry = SerializerRegistry.default()
        ser = registry.get_by_type_name("numpy.ndarray")
        assert isinstance(ser, NumpySerializer)

    def test_get_by_type_name_fallback_pickle(self) -> None:
        registry = SerializerRegistry()
        ser = registry.get_by_type_name("some.Unknown")
        assert isinstance(ser, PickleSerializer)
