"""Round-trip and validation tests for :class:`OnnxFormat`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import onnx  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("onnx not installed") from _e

import onnx as _onnx
from onnx import TensorProto, helper

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.onnx_format import OnnxFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_tiny_model() -> bytes:
    """Build a minimal valid ONNX model: identity on a 2-element float vector."""
    input_value = helper.make_tensor_value_info(
        "x", TensorProto.FLOAT, [2]
    )
    output_value = helper.make_tensor_value_info(
        "y", TensorProto.FLOAT, [2]
    )
    identity_node = helper.make_node("Identity", ["x"], ["y"])
    graph = helper.make_graph(
        [identity_node], "tiny", [input_value], [output_value]
    )
    opset = helper.make_opsetid("", 17)
    model = helper.make_model(
        graph, producer_name="pirn-test", opset_imports=[opset]
    )
    model.ir_version = 9
    _onnx.checker.check_model(model)
    return model.SerializeToString()


class TestOnnxFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = OnnxFormat()
        assert fmt.validate is True

    def test_explicit_validate_false(self) -> None:
        fmt = OnnxFormat(validate=False)
        assert fmt.validate is False

    def test_non_bool_validate_rejected(self) -> None:
        with self.assertRaises(TypeError):
            OnnxFormat(validate="yes")  # type: ignore[arg-type]


class TestOnnxFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert OnnxFormat().name == "onnx"

    def test_streaming_property(self) -> None:
        assert OnnxFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(OnnxFormat(), BatchFileFormat)


class TestOnnxFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        payload = _make_tiny_model()
        fmt = OnnxFormat()
        body = await FormatRoundTrip.encode(
            fmt, [{"model_bytes": payload}]
        )
        decoded = await FormatRoundTrip.decode(fmt, body)
        assert len(decoded) == 1
        record: dict[str, Any] = dict(decoded[0])
        assert record["model_bytes"] == payload
        assert record["ir_version"] == 9
        assert record["producer_name"] == "pirn-test"
        assert record["graph_inputs"] == ["x"]
        assert record["graph_outputs"] == ["y"]
        assert record["node_count"] == 1

    async def test_decode_rejects_garbage(self) -> None:
        fmt = OnnxFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(fmt, b"not-an-onnx-model")

    async def test_encode_requires_model_bytes_key(self) -> None:
        fmt = OnnxFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"wrong": b"x"}])

    async def test_encode_rejects_invalid_bytes(self) -> None:
        fmt = OnnxFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"model_bytes": b"junk"}]
            )

    async def test_encode_empty_records_rejected(self) -> None:
        fmt = OnnxFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_validate_false_skips_checker(self) -> None:
        # A model with ir_version that the checker would still accept,
        # so this primarily exercises the no-validate branch.
        payload = _make_tiny_model()
        fmt = OnnxFormat(validate=False)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["model_bytes"] == payload
