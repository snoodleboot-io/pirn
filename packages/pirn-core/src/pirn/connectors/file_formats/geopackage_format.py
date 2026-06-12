"""``GeopackageFormat`` — GeoPackage (``.gpkg``) encoder/decoder.

Backed by ``fiona`` (which wraps OGR). GeoPackage is a SQLite database
that stores one or more vector layers; this format reads and writes a
single named layer.

Each record corresponds to one feature::

    {
        "geometry":   Mapping[str, Any],
        "properties": Mapping[str, Any],
    }

Round-trip fidelity matches what fiona/OGR's GPKG driver preserves —
property types are coerced to fit the inferred schema; tests assert
structural and value survival of simple Point/property fixtures.

Install: ``pip install pirn[geopackage]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class GeopackageFormat(BatchFileFormat):
    """Whole-file GeoPackage encoder/decoder backed by ``fiona``."""

    def __init__(self, layer_name: str = "default") -> None:
        if not isinstance(layer_name, str):
            raise TypeError(
                f"GeopackageFormat: layer_name must be a string, got {type(layer_name).__name__}"
            )
        if not layer_name:
            raise ValueError("GeopackageFormat: layer_name must be non-empty")
        self._layer_name = layer_name

    @property
    def name(self) -> str:
        return "geopackage"

    @property
    def layer_name(self) -> str:
        return self._layer_name

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        fiona = self._load_fiona()
        path = self._materialise_payload(payload)
        try:
            with fiona.open(path, layer=self._layer_name) as source:
                records: list[Mapping[str, Any]] = []
                for feature in source:
                    geometry = self._geometry_to_mapping(feature)
                    properties = self._properties_to_mapping(feature)
                    records.append(
                        {
                            "geometry": geometry,
                            "properties": properties,
                        }
                    )
            return records
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        fiona = self._load_fiona()
        materialised: list[Mapping[str, Any]] = list(records)
        if not materialised:
            raise ValueError(
                "GeopackageFormat: cannot encode an empty record set; "
                "GeoPackage requires at least one feature to infer "
                "schema"
            )
        for record in materialised:
            self._validate_record(record)
        schema = self._infer_schema(materialised[0])
        path = self._reserve_path()
        try:
            with fiona.open(
                path,
                "w",
                driver="GPKG",
                layer=self._layer_name,
                schema=schema,
            ) as sink:
                for record in materialised:
                    sink.write(
                        {
                            "geometry": dict(record["geometry"]),
                            "properties": dict(record.get("properties") or {}),
                        }
                    )
            with open(path, "rb") as handle:
                return handle.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @staticmethod
    def _materialise_payload(payload: bytes) -> str:
        descriptor, path = tempfile.mkstemp(suffix=".gpkg")
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
        descriptor, path = tempfile.mkstemp(suffix=".gpkg")
        os.close(descriptor)
        # GPKG driver prefers a non-existent path on create.
        try:
            os.unlink(path)
        except OSError:
            pass
        return path

    @staticmethod
    def _geometry_to_mapping(feature: Any) -> Mapping[str, Any]:
        geometry = feature["geometry"]
        if geometry is None:
            return {}
        if isinstance(geometry, Mapping):
            return dict(geometry)
        as_dict = getattr(geometry, "__geo_interface__", None)
        if as_dict is not None:
            return dict(as_dict)
        return {
            "type": getattr(geometry, "type", ""),
            "coordinates": getattr(geometry, "coordinates", None),
        }

    @staticmethod
    def _properties_to_mapping(feature: Any) -> Mapping[str, Any]:
        properties = feature["properties"]
        if properties is None:
            return {}
        return dict(properties)

    @classmethod
    def _validate_record(cls, record: Mapping[str, Any]) -> None:
        if "geometry" not in record:
            raise ValueError("GeopackageFormat: record missing required 'geometry' field")
        geometry = record["geometry"]
        if not isinstance(geometry, Mapping):
            raise TypeError(
                f"GeopackageFormat: geometry must be a Mapping, got {type(geometry).__name__}"
            )
        if "type" not in geometry:
            raise ValueError("GeopackageFormat: geometry must contain a 'type' field")

    @classmethod
    def _infer_schema(cls, sample: Mapping[str, Any]) -> Mapping[str, Any]:
        geometry_type = str(sample["geometry"]["type"])
        properties = sample.get("properties") or {}
        property_schema: dict[str, str] = {}
        for key, value in properties.items():
            property_schema[str(key)] = cls._fiona_type(value)
        return {
            "geometry": geometry_type,
            "properties": property_schema,
        }

    @staticmethod
    def _fiona_type(value: Any) -> str:
        if isinstance(value, bool):
            # Fiona treats booleans as ints under the GPKG driver.
            return "int"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "str"

    @staticmethod
    def _load_fiona() -> Any:
        try:
            import fiona
        except ImportError as exc:
            raise ImportError(
                "GeopackageFormat requires fiona. Install with `pip install pirn[geopackage]`."
            ) from exc
        return fiona
