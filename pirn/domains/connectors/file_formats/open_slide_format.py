"""``OpenSlideFormat`` — Whole-slide imaging (WSI) batch decoder.

OpenSlide supports a variety of WSI formats (SVS, NDPI, SCN, TIFF
pyramids, etc.). This format is READ ONLY — encoding raises
:class:`NotImplementedError`.

Records are emitted as ONE record per pyramid level::

    {
        "level":       int,
        "dimensions":  tuple[int, int],   # (width, height) at this level
        "downsample":  float,
        "tile_size":   int,               # configured tile size
        "data":        bytes | None,      # RGB bytes if level fits threshold
    }

PHI note: some WSI files embed patient metadata in vendor tags. Known
PHI metadata keys are stripped before records are emitted.

Install: ``pip install pirn[health]`` (requires OpenSlide C library).
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class OpenSlideFormat(BatchFileFormat):
    """Read-only whole-slide image decoder backed by ``openslide-python``.

    Args:
        tile_size: Tile size in pixels used when recording ``tile_size``
            in each level record. Default 256.
        max_decode_pixels: If set, levels whose total pixel count
            (width x height) is <= this value will have their raw RGB
            bytes materialised into the ``data`` field. Levels above
            the threshold emit ``data=None``. If ``None`` (default),
            ``data`` is always ``None``.
    """

    _phi_metadata_keys: ClassVar[frozenset[str]] = frozenset(
        {
            "aperio.Patient",
            "aperio.PatientName",
            "aperio.PatientID",
            "openslide.comment",
            "hamamatsu.Reference",
            "leica.Identifier",
            "mirax.SLIDE_BARCODE",
        }
    )

    def __init__(
        self,
        tile_size: int = 256,
        max_decode_pixels: int | None = None,
    ) -> None:
        if not isinstance(tile_size, int) or tile_size <= 0:
            raise ValueError(
                f"OpenSlideFormat: tile_size must be a positive int, got {tile_size!r}"
            )
        if max_decode_pixels is not None and (
            not isinstance(max_decode_pixels, int) or max_decode_pixels <= 0
        ):
            raise ValueError(
                "OpenSlideFormat: max_decode_pixels must be a positive int "
                f"or None, got {max_decode_pixels!r}"
            )
        self._tile_size = tile_size
        self._max_decode_pixels = max_decode_pixels

    @property
    def name(self) -> str:
        return "open_slide"

    @property
    def tile_size(self) -> int:
        return self._tile_size

    @property
    def max_decode_pixels(self) -> int | None:
        return self._max_decode_pixels

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        openslide = self._load_openslide()
        records: list[Mapping[str, Any]] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            # OpenSlide identifies format from file extension; use .tiff
            # as a broadly-accepted extension for synthetic fixtures.
            path = Path(tmpdir) / "slide.tiff"
            path.write_bytes(payload)
            slide = openslide.OpenSlide(str(path))
            try:
                for level in range(slide.level_count):
                    dimensions: tuple[int, int] = slide.level_dimensions[level]
                    downsample: float = slide.level_downsamples[level]
                    data: bytes | None = None
                    if self._max_decode_pixels is not None:
                        total_pixels = dimensions[0] * dimensions[1]
                        if total_pixels <= self._max_decode_pixels:
                            data = self._read_level_bytes(slide, level, dimensions)
                    records.append(
                        {
                            "level": level,
                            "dimensions": dimensions,
                            "downsample": downsample,
                            "tile_size": self._tile_size,
                            "data": data,
                        }
                    )
            finally:
                slide.close()
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        raise NotImplementedError("OpenSlideFormat: write is not supported")

    @staticmethod
    def _read_level_bytes(slide: Any, level: int, dimensions: tuple[int, int]) -> bytes:
        region = slide.read_region((0, 0), level, dimensions)
        rgb = region.convert("RGB")
        return rgb.tobytes()

    @classmethod
    def _strip_phi_metadata(cls, properties: Mapping[str, str]) -> dict[str, str]:
        return {k: v for k, v in properties.items() if k not in cls._phi_metadata_keys}

    @staticmethod
    def _load_openslide() -> Any:
        try:
            import openslide
        except ImportError as exc:
            raise ImportError(
                "OpenSlideFormat requires openslide-python and the "
                "OpenSlide C library. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return openslide
