"""``KmlFormat`` — Keyhole Markup Language (KML) encoder/decoder.

Writes use ``simplekml``: a compact builder API for emitting standards-
compliant KML XML. Reads use ``lxml`` to parse arbitrary KML and project
each ``<Placemark>`` into a record::

    {
        "name":          str,
        "description":   str,
        "geometry_type": str,           # "Point" | "LineString" | "Polygon" | ...
        "coordinates":   list[tuple],   # parsed (x, y[, z]) tuples
        "extended_data": Mapping[str, str],
    }

Round-trip preserves these fields. Numeric geometry components are
parsed as ``float`` and re-emitted by ``simplekml`` with whatever
precision it chooses; tests assert structural / value survival rather
than byte-identity.

Install: ``pip install pirn[kml]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class KmlFormat(BatchFileFormat):
    """Whole-document KML encoder/decoder."""

    _kml_namespace: ClassVar[str] = "http://www.opengis.net/kml/2.2"
    _supported_geometries: ClassVar[frozenset[str]] = frozenset({"Point", "LineString", "Polygon"})

    @property
    def name(self) -> str:
        return "kml"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        etree = self._load_lxml()
        if not payload.strip():
            return []
        root = etree.fromstring(payload)
        records: list[Mapping[str, Any]] = []
        placemark_tag = f"{{{self._kml_namespace}}}Placemark"
        for placemark in root.iter(placemark_tag):
            records.append(self._parse_placemark(placemark))
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        simplekml = self._load_simplekml()
        document = simplekml.Kml()
        for record in records:
            self._add_placemark(document, record)
        return document.kml().encode("utf-8")

    @classmethod
    def _parse_placemark(cls, placemark: Any) -> Mapping[str, Any]:
        name_el = cls._find_child(placemark, "name")
        description_el = cls._find_child(placemark, "description")
        geometry_type, coordinates = cls._parse_geometry(placemark)
        extended_data = cls._parse_extended_data(placemark)
        return {
            "name": name_el.text if name_el is not None else "",
            "description": (description_el.text if description_el is not None else ""),
            "geometry_type": geometry_type,
            "coordinates": coordinates,
            "extended_data": extended_data,
        }

    @classmethod
    def _parse_geometry(cls, placemark: Any) -> tuple[str, list[tuple[float, ...]]]:
        for geometry_type in cls._supported_geometries:
            element = cls._find_child(placemark, geometry_type)
            if element is None:
                continue
            coords_el = cls._find_descendant(element, "coordinates")
            if coords_el is None or not coords_el.text:
                return geometry_type, []
            coordinates = cls._parse_coordinate_string(coords_el.text)
            return geometry_type, coordinates
        return "", []

    @staticmethod
    def _parse_coordinate_string(
        text: str,
    ) -> list[tuple[float, ...]]:
        coordinates: list[tuple[float, ...]] = []
        for token in text.strip().split():
            parts = token.split(",")
            if not parts or not parts[0]:
                continue
            try:
                values = tuple(float(part) for part in parts if part)
            except ValueError as exc:
                raise ValueError(f"KmlFormat: invalid coordinate token {token!r}") from exc
            coordinates.append(values)
        return coordinates

    @classmethod
    def _parse_extended_data(cls, placemark: Any) -> Mapping[str, str]:
        extended = cls._find_child(placemark, "ExtendedData")
        if extended is None:
            return {}
        result: dict[str, str] = {}
        data_tag = f"{{{cls._kml_namespace}}}Data"
        value_tag = f"{{{cls._kml_namespace}}}value"
        for data_el in extended.iter(data_tag):
            key = data_el.get("name")
            if key is None:
                continue
            value_el = data_el.find(value_tag)
            result[str(key)] = value_el.text if value_el is not None and value_el.text else ""
        return result

    @classmethod
    def _add_placemark(cls, document: Any, record: Mapping[str, Any]) -> None:
        cls._validate_record(record)
        geometry_type = record["geometry_type"]
        coordinates = record["coordinates"]
        name = record.get("name", "")
        description = record.get("description", "")
        extended_data = record.get("extended_data") or {}
        if geometry_type == "Point":
            placemark = document.newpoint(name=name, description=description)
            placemark.coords = list(coordinates)
        elif geometry_type == "LineString":
            placemark = document.newlinestring(name=name, description=description)
            placemark.coords = list(coordinates)
        elif geometry_type == "Polygon":
            placemark = document.newpolygon(name=name, description=description)
            placemark.outerboundaryis = list(coordinates)
        else:
            raise ValueError(
                "KmlFormat: unsupported geometry_type "
                f"{geometry_type!r}; supported: "
                f"{sorted(cls._supported_geometries)}"
            )
        for key, value in extended_data.items():
            placemark.extendeddata.newdata(str(key), str(value))

    @classmethod
    def _validate_record(cls, record: Mapping[str, Any]) -> None:
        if "geometry_type" not in record:
            raise ValueError("KmlFormat: record missing required 'geometry_type'")
        if "coordinates" not in record:
            raise ValueError("KmlFormat: record missing required 'coordinates'")
        geometry_type = record["geometry_type"]
        if not isinstance(geometry_type, str):
            raise TypeError(
                f"KmlFormat: geometry_type must be a string, got {type(geometry_type).__name__}"
            )
        coordinates = record["coordinates"]
        if not isinstance(coordinates, (list, tuple)):
            raise TypeError(
                f"KmlFormat: coordinates must be a list/tuple, got {type(coordinates).__name__}"
            )

    @classmethod
    def _find_child(cls, element: Any, local_name: str) -> Any:
        return element.find(f"{{{cls._kml_namespace}}}{local_name}")

    @classmethod
    def _find_descendant(cls, element: Any, local_name: str) -> Any:
        return element.find(f".//{{{cls._kml_namespace}}}{local_name}")

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError(
                "KmlFormat requires lxml. Install with `pip install pirn[kml]`."
            ) from exc
        return etree

    @staticmethod
    def _load_simplekml() -> Any:
        try:
            import simplekml
        except ImportError as exc:
            raise ImportError(
                "KmlFormat requires simplekml. Install with `pip install pirn[kml]`."
            ) from exc
        return simplekml
