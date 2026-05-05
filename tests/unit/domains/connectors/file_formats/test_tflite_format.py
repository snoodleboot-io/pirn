"""Round-trip and validation tests for :class:`TfliteFormat`.

The TFLite interpreter ships with both ``tflite_runtime`` and the full
``tensorflow`` install. Construction tests run unconditionally; tests
that decode a real model skip when neither runtime is available.
"""

from __future__ import annotations

import importlib.util
import unittest

import pytest

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.tflite_format import TfliteFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _has_tflite_runtime() -> bool:
    return (
        importlib.util.find_spec("tflite_runtime") is not None
        or importlib.util.find_spec("tensorflow") is not None
    )


class TestTfliteFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = TfliteFormat()
        assert fmt.name == "tflite"


class TestTfliteFormatBasics(unittest.TestCase):
    def test_streaming_property(self) -> None:
        assert TfliteFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(TfliteFormat(), BatchFileFormat)


class TestTfliteFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_decode_non_bytes_rejected(self) -> None:
        fmt = TfliteFormat()
        with self.assertRaises(TypeError):
            await fmt._decode_full("not-bytes")  # type: ignore[arg-type]

    async def test_encode_empty_rejected(self) -> None:
        fmt = TfliteFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_encode_missing_model_bytes_rejected(self) -> None:
        fmt = TfliteFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"wrong": b"x"}])

    async def test_encode_non_bytes_rejected(self) -> None:
        fmt = TfliteFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(
                fmt, [{"model_bytes": "not-bytes"}]
            )

    async def test_encode_emits_bytes_verbatim(self) -> None:
        fmt = TfliteFormat()
        # Encode-only path doesn't need the SDK; just verify pass-through.
        body = await FormatRoundTrip.encode(
            fmt, [{"model_bytes": b"abc"}]
        )
        assert body == b"abc"


@pytest.mark.skipif(
    not _has_tflite_runtime(),
    reason="requires tflite_runtime or tensorflow",
)
class TestTfliteFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        try:
            import tensorflow
        except ImportError as _e:
            self.skipTest("tensorflow not installed")
        # Build a tiny model and convert to TFLite to get valid bytes.
        model = tf.keras.Sequential(
            [tf.keras.layers.Dense(2, input_shape=(2,))]
        )
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        tflite_bytes = converter.convert()
        fmt = TfliteFormat()
        payload = await FormatRoundTrip.encode(
            fmt, [{"model_bytes": tflite_bytes}]
        )
        assert payload == bytes(tflite_bytes)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        record = decoded[0]
        assert record["model_bytes"] == bytes(tflite_bytes)
        assert isinstance(record["input_details"], list)
        assert isinstance(record["output_details"], list)
        assert len(record["input_details"]) == 1
        assert len(record["output_details"]) == 1
        assert record["version"] == 3
