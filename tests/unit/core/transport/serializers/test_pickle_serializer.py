"""Unit tests for :class:`PickleSerializer`."""

from __future__ import annotations

import unittest

from pirn.core.transport.serializers.pickle_serializer import PickleSerializer
from pirn.core.transport.serializers.serialiser_error import SerialiserError


class TestPickleSerializer(unittest.TestCase):
    def setUp(self) -> None:
        self.ser = PickleSerializer()

    def test_can_handle_returns_true_for_any_value(self) -> None:
        for value in (42, "hello", [1, 2], {"a": 1}, None, object()):
            with self.subTest(value=type(value).__name__):
                assert self.ser.can_handle(value)

    def test_round_trip_dict(self) -> None:
        value = {"patient_id": "P1", "score": 0.95}
        raw = self.ser.serialise(value)
        assert isinstance(raw, bytes)
        result = self.ser.deserialise(raw, "dict")
        assert result == value

    def test_round_trip_list(self) -> None:
        value = [1.0, 2.0, 3.0]
        result = self.ser.deserialise(self.ser.serialise(value), "list")
        assert result == value

    def test_round_trip_nested(self) -> None:
        value = {"rows": [{"a": 1}, {"a": 2}], "count": 2}
        result = self.ser.deserialise(self.ser.serialise(value), "dict")
        assert result == value

    def test_deserialise_corrupted_data_raises(self) -> None:
        with self.assertRaises(SerialiserError):
            self.ser.deserialise(b"not-pickle", "dict")
