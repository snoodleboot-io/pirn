"""Round-trip and validation tests for :class:`HeicFormat`.

HEIC is a lossy codec — pixel-exactness is not asserted. Tests verify
``width``, ``height``, ``mode`` survive plus output bytes have the
expected raw length.
"""

from __future__ import annotations

import unittest

try:
    import PIL  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("PIL not installed") from _e
try:
    import pillow_heif  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pillow_heif not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.heic_format import (
    HeicFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _tiny_rgb_record() -> dict[str, object]:
    pixels: list[int] = []
    for y in range(4):
        for x in range(4):
            pixels.extend([x * 32, y * 32, (x + y) * 16])
    return {
        "width": 4,
        "height": 4,
        "mode": "RGB",
        "data": bytes(pixels),
    }


class TestHeicFormatConstruction(unittest.TestCase):
    def test_default_quality(self) -> None:
        fmt = HeicFormat()
        assert fmt.quality == 85

    def test_custom_quality(self) -> None:
        assert HeicFormat(quality=70).quality == 70

    def test_quality_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            HeicFormat(quality=0)
        with self.assertRaises(ValueError):
            HeicFormat(quality=101)

    def test_quality_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            HeicFormat(quality="high")  # type: ignore[arg-type]


class TestHeicFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert HeicFormat().name == "heic"

    def test_streaming_property(self) -> None:
        assert HeicFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(HeicFormat(), BatchFileFormat)


class TestHeicFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        record = _tiny_rgb_record()
        fmt = HeicFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        assert recovered["width"] == record["width"]
        assert recovered["height"] == record["height"]
        assert recovered["mode"] == record["mode"]
        assert isinstance(recovered["data"], bytes)
        assert len(recovered["data"]) == len(record["data"])

    async def test_round_trip_single_record(self) -> None:
        record = _tiny_rgb_record()
        fmt = HeicFormat(quality=70)
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1

    async def test_empty_records_rejected(self) -> None:
        fmt = HeicFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])
