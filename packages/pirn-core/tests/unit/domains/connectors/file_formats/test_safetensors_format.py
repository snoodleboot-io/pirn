"""Round-trip and validation tests for :class:`SafetensorsFormat`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import safetensors  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("safetensors not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

import numpy as np
from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.safetensors_format import (
    SafetensorsFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestSafetensorsFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = SafetensorsFormat()
        assert fmt.include_data is True

    def test_include_data_false(self) -> None:
        fmt = SafetensorsFormat(include_data=False)
        assert fmt.include_data is False

    def test_non_bool_include_data_rejected(self) -> None:
        with self.assertRaises(TypeError):
            SafetensorsFormat(include_data="yes")  # type: ignore[arg-type]


class TestSafetensorsFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert SafetensorsFormat().name == "safetensors"

    def test_streaming_property(self) -> None:
        assert SafetensorsFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(SafetensorsFormat(), BatchFileFormat)


class TestSafetensorsFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        weights = np.zeros((2, 2), dtype=np.float32)
        record = {
            "tensors": {"weights": weights},
            "metadata": {"layer": "dense_0", "framework": "test"},
        }
        fmt = SafetensorsFormat()
        body = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, body)
        assert len(decoded) == 1
        out: dict[str, Any] = dict(decoded[0])
        assert "weights" in out["tensors"]
        spec = out["tensors"]["weights"]
        assert spec["shape"] == [2, 2]
        assert spec["dtype"] == "float32"
        assert spec["data"] == [0.0, 0.0, 0.0, 0.0]
        assert out["metadata"] == {"layer": "dense_0", "framework": "test"}

    async def test_round_trip_via_spec_dict(self) -> None:
        record = {
            "tensors": {
                "w": {
                    "shape": [2, 2],
                    "dtype": "float32",
                    "data": [1.0, 2.0, 3.0, 4.0],
                }
            },
            "metadata": {},
        }
        fmt = SafetensorsFormat()
        body = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, body)
        spec = decoded[0]["tensors"]["w"]
        assert spec["shape"] == [2, 2]
        assert spec["dtype"] == "float32"
        assert spec["data"] == [1.0, 2.0, 3.0, 4.0]

    async def test_include_data_false_omits_data(self) -> None:
        weights = np.ones((3,), dtype=np.float32)
        encode_fmt = SafetensorsFormat()
        body = await FormatRoundTrip.encode(
            encode_fmt,
            [{"tensors": {"w": weights}, "metadata": {}}],
        )
        read_fmt = SafetensorsFormat(include_data=False)
        decoded = await FormatRoundTrip.decode(read_fmt, body)
        spec = decoded[0]["tensors"]["w"]
        assert spec["shape"] == [3]
        assert spec["dtype"] == "float32"
        assert "data" not in spec

    async def test_encode_empty_records_rejected(self) -> None:
        fmt = SafetensorsFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_encode_missing_tensors_key(self) -> None:
        fmt = SafetensorsFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"metadata": {}}])

    async def test_encode_rejects_non_string_metadata(self) -> None:
        fmt = SafetensorsFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "tensors": {
                            "w": np.zeros((1,), dtype=np.float32)
                        },
                        "metadata": {"layer": 1},
                    }
                ],
            )

    async def test_decode_rejects_garbage(self) -> None:
        fmt = SafetensorsFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(fmt, b"\x00\x00\x00not-real")
