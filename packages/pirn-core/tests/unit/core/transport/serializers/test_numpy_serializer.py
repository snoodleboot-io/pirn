"""Unit tests for :class:`NumpySerializer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.transport.serializers.numpy_serializer import NumpySerializer
from pirn.core.transport.serializers.serialiser_error import SerialiserError


class TestNumpySerializer(unittest.TestCase):
    def setUp(self) -> None:
        self.ser = NumpySerializer()

    def test_can_handle_ndarray(self) -> None:
        assert self.ser.can_handle(np.array([1.0, 2.0]))

    def test_cannot_handle_plain_list(self) -> None:
        assert not self.ser.can_handle([1.0, 2.0])

    def test_round_trip_1d_float64(self) -> None:
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        raw = self.ser.serialise(arr)
        result = self.ser.deserialise(raw, "numpy.ndarray")
        np.testing.assert_array_equal(result, arr)

    def test_round_trip_2d_int32(self) -> None:
        arr = np.arange(12, dtype=np.int32).reshape(3, 4)
        raw = self.ser.serialise(arr)
        result = self.ser.deserialise(raw, "numpy.ndarray")
        np.testing.assert_array_equal(result, arr)

    def test_preserves_dtype(self) -> None:
        arr = np.array([1.0], dtype=np.float32)
        result = self.ser.deserialise(self.ser.serialise(arr), "numpy.ndarray")
        assert result.dtype == np.float32

    def test_deserialise_corrupted_data_raises(self) -> None:
        with self.assertRaises(SerialiserError):
            self.ser.deserialise(b"not-numpy", "numpy.ndarray")
