"""``JpegFormat`` — JPEG (JFIF) encoder/decoder.

Reads and writes use ``Pillow``. JPEG is a single-image lossy raster
container that requires whole-payload decoding, so this is a
:class:`BatchFileFormat`.

The format yields exactly one record per file with shape::

    {
        "width":  int,
        "height": int,
        "mode":   str,    # e.g. "RGB", "L"
        "data":   bytes,  # raw pixel bytes from PIL.Image.tobytes()
    }

Encoding takes the first record from the input stream and ignores the
rest — JPEG cannot multiplex multiple images.

Round-trip is **LOSSY**. Pixel-exactness is not preserved by the JPEG
codec; tests should assert ``width``, ``height`` and ``mode`` survive,
but must not compare ``data`` byte-for-byte.

Security: pirn does not sandbox ``Pillow``. Malformed payloads may
trigger upstream library bugs (decompression bombs, malformed segments).
Treat untrusted payloads accordingly.

Install: ``pip install pirn[image]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class JpegFormat(BatchFileFormat):
    """Whole-file JPEG encoder/decoder."""

    def __init__(self, quality: int = 95) -> None:
        if not isinstance(quality, int) or isinstance(quality, bool):
            raise TypeError(f"JpegFormat: quality must be an int, got {type(quality).__name__}")
        if quality < 1 or quality > 100:
            raise ValueError(f"JpegFormat: quality must be in [1, 100], got {quality}")
        self._quality = quality

    @property
    def name(self) -> str:
        return "jpeg"

    @property
    def quality(self) -> int:
        return self._quality

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"JpegFormat: payload must be bytes, got {type(payload).__name__}")
        pil_image = self._load_pil_image()
        with pil_image.open(io.BytesIO(payload)) as image:
            image.load()
            return [
                {
                    "width": int(image.width),
                    "height": int(image.height),
                    "mode": str(image.mode),
                    "data": image.tobytes(),
                }
            ]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised:
            raise ValueError(
                "JpegFormat: cannot encode an empty record stream — "
                "JPEG requires exactly one image per file."
            )
        record = materialised[0]
        width, height, mode, data = self._validate_record(record)
        pil_image = self._load_pil_image()
        image = pil_image.frombytes(mode, (width, height), data)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=self._quality)
        return buf.getvalue()

    @staticmethod
    def _validate_record(
        record: Mapping[str, Any],
    ) -> tuple[int, int, str, bytes]:
        for field in ("width", "height", "mode", "data"):
            if field not in record:
                raise ValueError(
                    "JpegFormat: record missing required field "
                    f"{field!r} — got keys {list(record.keys())}"
                )
        width = record["width"]
        height = record["height"]
        mode = record["mode"]
        data = record["data"]
        if not isinstance(width, int) or width <= 0:
            raise ValueError(f"JpegFormat: 'width' must be a positive int, got {width!r}")
        if not isinstance(height, int) or height <= 0:
            raise ValueError(f"JpegFormat: 'height' must be a positive int, got {height!r}")
        if not isinstance(mode, str) or not mode:
            raise ValueError(f"JpegFormat: 'mode' must be a non-empty string, got {mode!r}")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"JpegFormat: 'data' must be bytes, got {type(data).__name__}")
        return width, height, mode, bytes(data)

    @staticmethod
    def _load_pil_image() -> Any:
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "JpegFormat requires Pillow. Install with `pip install pirn[image]`."
            ) from exc
        return Image
