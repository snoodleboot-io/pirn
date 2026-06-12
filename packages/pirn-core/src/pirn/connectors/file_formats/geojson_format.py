"""``GeoJsonFormat`` — GeoJSON FeatureCollection encoder/decoder.

GeoJSON is JSON, so the standard library ``json`` module is sufficient
for encode/decode. The ``geojson`` package is optionally accepted when
present (it produces equivalent dicts), but not required at runtime —
the import is lazy and ``json`` is used as the ground truth.

Each record corresponds to one ``Feature`` and has the shape::

    {
        "geometry":   Mapping[str, Any] | None,
        "properties": Mapping[str, Any],
        "feature_id": str | None,
    }

Strictly speaking GeoJSON cannot be decoded incrementally (the whole
document must be parsed before yielding ``features``). It inherits from
:class:`StreamingFileFormat` for API consistency with :class:`JsonFormat`;
downstream consumers should treat ``streaming`` only as advisory.

Install: ``pip install pirn[geojson]``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class GeoJsonFormat(StreamingFileFormat):
    """GeoJSON ``FeatureCollection`` encoder/decoder."""

    def __init__(self, encoding: str = "utf-8") -> None:
        if not isinstance(encoding, str):
            raise TypeError(f"GeoJsonFormat: encoding must be str, got {type(encoding).__name__}")
        if not encoding:
            raise ValueError("GeoJsonFormat: encoding must be non-empty")
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "geojson"

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]:
        payload = await self._drain_bytes(body)
        if not payload.strip():
            features: list[Mapping[str, Any]] = []
        else:
            parsed = json.loads(payload.decode(self._encoding))
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"GeoJsonFormat: expected JSON object at root, got {type(parsed).__name__}"
                )
            type_value = parsed.get("type")
            if type_value != "FeatureCollection":
                raise ValueError(
                    f"GeoJsonFormat: expected type='FeatureCollection', got {type_value!r}"
                )
            raw_features = parsed.get("features", [])
            if not isinstance(raw_features, list):
                raise ValueError(
                    f"GeoJsonFormat: 'features' must be a list, got {type(raw_features).__name__}"
                )
            features = [self._feature_to_record(feature) for feature in raw_features]

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for record in features:
                yield record

        return _iter()

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]:
        materialised = await self._drain_records(records)
        feature_dicts: list[Mapping[str, Any]] = []
        for record in materialised:
            feature_dicts.append(self._record_to_feature(record))
        document = {"type": "FeatureCollection", "features": feature_dicts}
        payload = json.dumps(document).encode(self._encoding)

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()

    @staticmethod
    def _feature_to_record(feature: Any) -> Mapping[str, Any]:
        if not isinstance(feature, dict):
            raise ValueError(
                f"GeoJsonFormat: each feature must be a JSON object, got {type(feature).__name__}"
            )
        if feature.get("type") != "Feature":
            raise ValueError(
                f"GeoJsonFormat: feature missing type='Feature', got {feature.get('type')!r}"
            )
        geometry = feature.get("geometry")
        if geometry is not None and not isinstance(geometry, dict):
            raise ValueError(
                "GeoJsonFormat: geometry must be a JSON object or null, "
                f"got {type(geometry).__name__}"
            )
        properties = feature.get("properties") or {}
        if not isinstance(properties, dict):
            raise ValueError(
                f"GeoJsonFormat: properties must be a JSON object, got {type(properties).__name__}"
            )
        feature_id = feature.get("id")
        return {
            "geometry": geometry,
            "properties": properties,
            "feature_id": (None if feature_id is None else str(feature_id)),
        }

    @staticmethod
    def _record_to_feature(record: Mapping[str, Any]) -> Mapping[str, Any]:
        if "geometry" not in record:
            raise ValueError("GeoJsonFormat: record missing required 'geometry' field")
        geometry = record["geometry"]
        if geometry is not None and not isinstance(geometry, Mapping):
            raise TypeError(
                f"GeoJsonFormat: geometry must be a Mapping or None, got {type(geometry).__name__}"
            )
        properties = record.get("properties") or {}
        if not isinstance(properties, Mapping):
            raise TypeError(
                f"GeoJsonFormat: properties must be a Mapping, got {type(properties).__name__}"
            )
        feature: dict[str, Any] = {
            "type": "Feature",
            "geometry": (None if geometry is None else dict(geometry)),
            "properties": dict(properties),
        }
        feature_id = record.get("feature_id")
        if feature_id is not None:
            feature["id"] = feature_id
        return feature
