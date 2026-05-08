"""``GeotiffFormat`` — GeoTIFF raster encoder/decoder.

Backed by ``rasterio``. Each record corresponds to one raster band::

    {
        "band_number": int,
        "data":        list,            # row-major flattened pixels
        "transform":   Mapping,         # affine coefficients (a..f)
        "crs":         str,             # CRS as a string ("EPSG:4326", ...)
        "width":       int,
        "height":      int,
        "dtype":       str,             # numpy dtype name
    }

Round-trip is only guaranteed for pixel data: rasterio normalises
``transform`` and ``crs`` representations on write, so byte-identity is
not preserved. Tests assert pixel-data and shape survival.

GeoTIFF cannot be decoded incrementally without seekable storage —
inherits from :class:`BatchFileFormat`.

Install: ``pip install pirn[geotiff]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class GeotiffFormat(BatchFileFormat):
    """Whole-file GeoTIFF encoder/decoder backed by ``rasterio``."""

    @property
    def name(self) -> str:
        return "geotiff"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        rasterio = self._load_rasterio()
        path = self._materialise_payload(payload)
        try:
            with rasterio.open(path) as dataset:
                transform_mapping = self._transform_to_mapping(dataset.transform)
                crs_repr = str(dataset.crs) if dataset.crs is not None else ""
                width = int(dataset.width)
                height = int(dataset.height)
                records: list[Mapping[str, Any]] = []
                for band_number in range(1, dataset.count + 1):
                    array = dataset.read(band_number)
                    records.append(
                        {
                            "band_number": band_number,
                            "data": array.flatten().tolist(),
                            "transform": transform_mapping,
                            "crs": crs_repr,
                            "width": width,
                            "height": height,
                            "dtype": str(array.dtype),
                        }
                    )
            return records
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        rasterio = self._load_rasterio()
        numpy = self._load_numpy()
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised:
            raise ValueError(
                "GeotiffFormat: cannot encode an empty record set; "
                "GeoTIFF requires at least one band"
            )
        first_record = materialised[0]
        self._validate_record(first_record)
        width = int(first_record["width"])
        height = int(first_record["height"])
        if width <= 0 or height <= 0:
            raise ValueError(
                "GeotiffFormat: width and height must be positive, "
                f"got width={width} height={height}"
            )
        transform = self._transform_from_mapping(rasterio, first_record.get("transform"))
        if not first_record.get("crs"):
            raise KeyError(
                f"GeotiffFormat: record missing required field 'crs'; got: {list(first_record)}"
            )
        crs_value = first_record["crs"]
        dtype = first_record.get("dtype", "float64")
        path = self._reserve_path()
        try:
            profile = {
                "driver": "GTiff",
                "width": width,
                "height": height,
                "count": len(materialised),
                "dtype": dtype,
                "transform": transform,
            }
            if crs_value:
                profile["crs"] = crs_value
            with rasterio.open(path, "w", **profile) as dataset:
                for index, record in enumerate(materialised, start=1):
                    self._validate_record(record)
                    band_data = numpy.asarray(record["data"], dtype=dtype).reshape(height, width)
                    dataset.write(band_data, index)
            with open(path, "rb") as handle:
                return handle.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @staticmethod
    def _materialise_payload(payload: bytes) -> str:
        descriptor, path = tempfile.mkstemp(suffix=".tif")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        return path

    @staticmethod
    def _reserve_path() -> str:
        descriptor, path = tempfile.mkstemp(suffix=".tif")
        os.close(descriptor)
        return path

    @staticmethod
    def _transform_to_mapping(transform: Any) -> Mapping[str, float]:
        coefficients = list(transform)
        keys = ("a", "b", "c", "d", "e", "f")
        return {
            key: float(coefficients[index]) for index, key in enumerate(keys[: len(coefficients)])
        }

    @staticmethod
    def _transform_from_mapping(rasterio: Any, mapping: Any) -> Any:
        from rasterio.transform import Affine

        if mapping is None:
            return Affine.identity()
        if not isinstance(mapping, Mapping):
            raise TypeError(
                f"GeotiffFormat: transform must be a Mapping, got {type(mapping).__name__}"
            )
        keys = ("a", "b", "c", "d", "e", "f")
        try:
            values = [float(mapping[key]) for key in keys]
        except KeyError as exc:
            raise ValueError(
                "GeotiffFormat: transform mapping missing required "
                f"key {exc.args[0]!r}; expected keys {list(keys)}"
            ) from exc
        return Affine(*values)

    @staticmethod
    def _validate_record(record: Mapping[str, Any]) -> None:
        for required in ("data", "width", "height"):
            if required not in record:
                raise ValueError(f"GeotiffFormat: record missing required field {required!r}")
        data = record["data"]
        if not isinstance(data, (list, tuple)):
            raise TypeError(
                "GeotiffFormat: 'data' must be a list/tuple of pixel "
                f"values, got {type(data).__name__}"
            )

    @staticmethod
    def _load_rasterio() -> Any:
        try:
            import rasterio
        except ImportError as exc:
            raise ImportError(
                "GeotiffFormat requires rasterio. Install with `pip install pirn[geotiff]`."
            ) from exc
        return rasterio

    @staticmethod
    def _load_numpy() -> Any:
        try:
            import numpy
        except ImportError as exc:
            raise ImportError(
                "GeotiffFormat requires numpy (transitively via "
                "rasterio). Install with `pip install pirn[geotiff]`."
            ) from exc
        return numpy
