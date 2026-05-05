"""Round-trip and validation tests for :class:`TfSavedModelFormat`."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import pytest

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.tf_saved_model_format import (
    TfSavedModelFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

_HAS_TF = importlib.util.find_spec("tensorflow") is not None


class TestTfSavedModelFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = TfSavedModelFormat()
        assert fmt.name == "tf_saved_model"


class TestTfSavedModelFormatBasics(unittest.TestCase):
    def test_streaming_property(self) -> None:
        assert TfSavedModelFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(TfSavedModelFormat(), BatchFileFormat)


class TestTfSavedModelFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_decode_non_bytes_rejected(self) -> None:
        fmt = TfSavedModelFormat()
        with self.assertRaises(TypeError):
            await fmt._decode_full("not-bytes")  # type: ignore[arg-type]

    async def test_encode_missing_path_rejected(self) -> None:
        fmt = TfSavedModelFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"wrong": 1}])

    async def test_encode_invalid_path_rejected(self) -> None:
        fmt = TfSavedModelFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"saved_model_path": "/nonexistent/path/xyz"}]
            )

    async def test_encode_empty_rejected(self) -> None:
        fmt = TfSavedModelFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])


@pytest.mark.skipif(not _HAS_TF, reason="requires tensorflow")
class TestTfSavedModelFormatRoundTrip(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        """Build a tiny SavedModel on disk and return the directory path."""
        import tensorflow as tf
        tmp = tempfile.mkdtemp(prefix="pirn-tf-fixture-")
        model = tf.keras.Sequential(
            [tf.keras.layers.Dense(2, input_shape=(2,))]
        )
        model.compile(optimizer="sgd", loss="mse")
        path = os.path.join(tmp, "saved_model")
        model.save(path, save_format="tf")
        self.saved_model_path = path
        
        
    async def test_round_trip_basic(self) -> None:
        saved_model_path = self.saved_model_path
        fmt = TfSavedModelFormat()
        payload = await FormatRoundTrip.encode(
            fmt, [{"saved_model_path": saved_model_path}]
        )
        assert payload[:2] == b"PK"  # ZIP magic
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        record = decoded[0]
        assert os.path.isdir(record["saved_model_path"])
        assert record["metadata"]["format"] == "tf_saved_model"
        # Keep the temp dir alive until the test ends.
        record["_tmpdir"].cleanup()
