"""``PngFormat`` — Portable Network Graphics (PNG) encoder/decoder.

Reads and writes use ``Pillow``. PNG is a single-image raster container
that requires whole-payload decoding, so this is a
:class:`BatchFileFormat`.

The format yields exactly one record per file with shape::

    {
        "width":  int,
        "height": int,
        "mode":   str,    # e.g. "RGB", "RGBA", "L"
        "data":   bytes,  # raw pixel bytes from PIL.Image.tobytes()
    }

Encoding takes the first record from the input stream and ignores the
rest — PNG cannot multiplex multiple images. Round-trip is lossless.

Security: pirn does not sandbox ``Pillow``. Malformed payloads may
trigger upstream library bugs (decompression bombs, malformed chunks).
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


class PngFormat(BatchFileFormat):
    """Whole-file PNG encoder/decoder."""

    @property
    def name(self) -> str:
        return "png"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"PngFormat: payload must be bytes, got {type(payload).__name__}")
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
                "PngFormat: cannot encode an empty record stream — "
                "PNG requires exactly one image per file."
            )
        record = materialised[0]
        width, height, mode, data = self._validate_record(record)
        pil_image = self._load_pil_image()
        image = pil_image.frombytes(mode, (width, height), data)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _validate_record(
        record: Mapping[str, Any],
    ) -> tuple[int, int, str, bytes]:
        for field in ("width", "height", "mode", "data"):
            if field not in record:
                raise ValueError(
                    "PngFormat: record missing required field "
                    f"{field!r} — got keys {list(record.keys())}"
                )
        width = record["width"]
        height = record["height"]
        mode = record["mode"]
        data = record["data"]
        if not isinstance(width, int) or width <= 0:
            raise ValueError(f"PngFormat: 'width' must be a positive int, got {width!r}")
        if not isinstance(height, int) or height <= 0:
            raise ValueError(f"PngFormat: 'height' must be a positive int, got {height!r}")
        if not isinstance(mode, str) or not mode:
            raise ValueError(f"PngFormat: 'mode' must be a non-empty string, got {mode!r}")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"PngFormat: 'data' must be bytes, got {type(data).__name__}")
        return width, height, mode, bytes(data)

    @staticmethod
    def _load_pil_image() -> Any:
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "PngFormat requires Pillow. Install with `pip install pirn[image]`."
            ) from exc
        return Image
