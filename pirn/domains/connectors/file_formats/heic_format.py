"""``HeicFormat`` — High Efficiency Image Container (HEIC/HEIF) encoder/decoder.

Reads and writes use ``pillow-heif`` (which registers HEIF support
into ``Pillow``). HEIC is a single-image raster container that requires
whole-payload decoding, so this is a :class:`BatchFileFormat`.

The format yields exactly one record per file with shape::

    {
        "width":  int,
        "height": int,
        "mode":   str,    # e.g. "RGB", "RGBA"
        "data":   bytes,  # raw pixel bytes from PIL.Image.tobytes()
    }

Encoding takes the first record from the input stream and ignores the
rest — multi-image HEIF (``.heif`` / iPhone Live Photos) is not
emitted.

Round-trip is **LOSSY**. Pixel-exactness is not preserved by the HEVC
codec used by HEIC; tests should assert ``width``, ``height`` and
``mode`` survive but must not compare ``data`` byte-for-byte.

Security: pirn does not sandbox ``pillow-heif`` / libheif. Malformed
payloads may trigger upstream library bugs. Treat untrusted payloads
accordingly.

Install: ``pip install pirn[heic]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class HeicFormat(BatchFileFormat):
    """Whole-file HEIC encoder/decoder."""

    def __init__(self, quality: int = 85) -> None:
        if not isinstance(quality, int) or isinstance(quality, bool):
            raise TypeError(
                "HeicFormat: quality must be an int, got "
                f"{type(quality).__name__}"
            )
        if quality < 1 or quality > 100:
            raise ValueError(
                "HeicFormat: quality must be in [1, 100], got "
                f"{quality}"
            )
        self._quality = quality

    @property
    def name(self) -> str:
        return "heic"

    @property
    def quality(self) -> int:
        return self._quality

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                "HeicFormat: payload must be bytes, got "
                f"{type(payload).__name__}"
            )
        pil_image = self._load_pil_image_with_heif()
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

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised:
            raise ValueError(
                "HeicFormat: cannot encode an empty record stream — "
                "HEIC requires exactly one image per file."
            )
        record = materialised[0]
        width, height, mode, data = self._validate_record(record)
        pil_image = self._load_pil_image_with_heif()
        image = pil_image.frombytes(mode, (width, height), data)
        buf = io.BytesIO()
        image.save(buf, format="HEIF", quality=self._quality)
        return buf.getvalue()

    @staticmethod
    def _validate_record(
        record: Mapping[str, Any],
    ) -> tuple[int, int, str, bytes]:
        for field in ("width", "height", "mode", "data"):
            if field not in record:
                raise ValueError(
                    "HeicFormat: record missing required field "
                    f"{field!r} — got keys {list(record.keys())}"
                )
        width = record["width"]
        height = record["height"]
        mode = record["mode"]
        data = record["data"]
        if not isinstance(width, int) or width <= 0:
            raise ValueError(
                "HeicFormat: 'width' must be a positive int, got "
                f"{width!r}"
            )
        if not isinstance(height, int) or height <= 0:
            raise ValueError(
                "HeicFormat: 'height' must be a positive int, got "
                f"{height!r}"
            )
        if not isinstance(mode, str) or not mode:
            raise ValueError(
                "HeicFormat: 'mode' must be a non-empty string, got "
                f"{mode!r}"
            )
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(
                "HeicFormat: 'data' must be bytes, got "
                f"{type(data).__name__}"
            )
        return width, height, mode, bytes(data)

    @staticmethod
    def _load_pil_image_with_heif() -> Any:
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "HeicFormat requires Pillow. Install with "
                "`pip install pirn[heic]`."
            ) from exc
        try:
            import pillow_heif
        except ImportError as exc:
            raise ImportError(
                "HeicFormat requires pillow-heif. Install with "
                "`pip install pirn[heic]`."
            ) from exc
        # Idempotent — pillow-heif guards against double registration.
        pillow_heif.register_heif_opener()
        return Image
