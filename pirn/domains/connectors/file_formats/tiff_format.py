"""``TiffFormat`` — Tagged Image File Format encoder/decoder.

Reads and writes use ``tifffile`` — the de-facto scientific TIFF
library — with ``Pillow`` available for ``mode`` derivation. TIFF is a
container that may hold multiple "pages" (subfiles / IFDs); this
implementation yields one record per page.

Each record has the shape::

    {
        "page_number": int,    # zero-based index within the file
        "width":       int,
        "height":      int,
        "mode":        str,    # e.g. "RGB", "L", "I;16"
        "data":        bytes,  # raw pixel bytes (numpy.tobytes())
        "dtype":       str,    # numpy dtype name, e.g. "uint8"
    }

Encoding accepts one or more records and writes a multi-page TIFF
(each record becomes a TIFF page). Round-trip is lossless when
``compression`` is ``None``, ``"lzw"`` or another lossless codec.

Security: pirn does not sandbox ``tifffile``. Malformed payloads may
trigger upstream library bugs. Treat untrusted payloads accordingly.

Install: ``pip install pirn[tiff]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class TiffFormat(BatchFileFormat):
    """Whole-file multi-page TIFF encoder/decoder."""

    def __init__(self, compression: str = "lzw") -> None:
        if not isinstance(compression, str) or not compression:
            raise ValueError(
                "TiffFormat: compression must be a non-empty string, "
                f"got {compression!r}"
            )
        self._compression = compression

    @property
    def name(self) -> str:
        return "tiff"

    @property
    def compression(self) -> str:
        return self._compression

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                "TiffFormat: payload must be bytes, got "
                f"{type(payload).__name__}"
            )
        tifffile = self._load_tifffile()
        records: list[Mapping[str, Any]] = []
        with tifffile.TiffFile(io.BytesIO(payload)) as tiff:
            for index, page in enumerate(tiff.pages):
                array = page.asarray()
                width, height, mode = self._derive_dimensions_and_mode(
                    array
                )
                records.append(
                    {
                        "page_number": index,
                        "width": width,
                        "height": height,
                        "mode": mode,
                        "data": array.tobytes(),
                        "dtype": str(array.dtype),
                    }
                )
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised:
            raise ValueError(
                "TiffFormat: cannot encode an empty record stream — "
                "TIFF requires at least one page."
            )
        tifffile = self._load_tifffile()
        numpy = self._load_numpy()
        arrays = [
            self._record_to_array(record, numpy)
            for record in materialised
        ]
        buf = io.BytesIO()
        tifffile.imwrite(
            buf,
            arrays if len(arrays) > 1 else arrays[0],
            compression=self._compression,
        )
        return buf.getvalue()

    @staticmethod
    def _derive_dimensions_and_mode(array: Any) -> tuple[int, int, str]:
        # tifffile arrays are (H, W) for greyscale, (H, W, C) for
        # multi-channel. Map to PIL-style mode strings for consumer
        # compatibility.
        if array.ndim == 2:
            height, width = array.shape
            mode = "L" if array.dtype.itemsize == 1 else "I;16"
        elif array.ndim == 3:
            height, width, channels = array.shape
            if channels == 3:
                mode = "RGB"
            elif channels == 4:
                mode = "RGBA"
            else:
                mode = f"MULTI{channels}"
        else:
            raise ValueError(
                "TiffFormat: unsupported page shape "
                f"{array.shape!r} — expected 2 or 3 dimensions"
            )
        return int(width), int(height), mode

    @staticmethod
    def _record_to_array(
        record: Mapping[str, Any], numpy: Any
    ) -> Any:
        for field in ("width", "height", "mode", "data", "dtype"):
            if field not in record:
                raise ValueError(
                    "TiffFormat: record missing required field "
                    f"{field!r} — got keys {list(record.keys())}"
                )
        width = record["width"]
        height = record["height"]
        mode = record["mode"]
        data = record["data"]
        dtype = record["dtype"]
        if not isinstance(width, int) or width <= 0:
            raise ValueError(
                "TiffFormat: 'width' must be a positive int, got "
                f"{width!r}"
            )
        if not isinstance(height, int) or height <= 0:
            raise ValueError(
                "TiffFormat: 'height' must be a positive int, got "
                f"{height!r}"
            )
        if not isinstance(mode, str) or not mode:
            raise ValueError(
                "TiffFormat: 'mode' must be a non-empty string, got "
                f"{mode!r}"
            )
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(
                "TiffFormat: 'data' must be bytes, got "
                f"{type(data).__name__}"
            )
        if not isinstance(dtype, str) or not dtype:
            raise ValueError(
                "TiffFormat: 'dtype' must be a non-empty string, got "
                f"{dtype!r}"
            )
        # Reconstruct shape from mode.
        if mode in ("L", "I;16"):
            shape: tuple[int, ...] = (height, width)
        elif mode == "RGB":
            shape = (height, width, 3)
        elif mode == "RGBA":
            shape = (height, width, 4)
        elif mode.startswith("MULTI"):
            channels = int(mode.removeprefix("MULTI"))
            shape = (height, width, channels)
        else:
            raise ValueError(
                f"TiffFormat: unsupported mode {mode!r} for encode"
            )
        array = numpy.frombuffer(bytes(data), dtype=dtype).reshape(
            shape
        )
        return array

    @staticmethod
    def _load_tifffile() -> Any:
        try:
            import tifffile
        except ImportError as exc:
            raise ImportError(
                "TiffFormat requires tifffile. Install with "
                "`pip install pirn[tiff]`."
            ) from exc
        return tifffile

    @staticmethod
    def _load_numpy() -> Any:
        try:
            import numpy
        except ImportError as exc:
            raise ImportError(
                "TiffFormat requires numpy (pulled in by tifffile). "
                "Install with `pip install pirn[tiff]`."
            ) from exc
        return numpy
