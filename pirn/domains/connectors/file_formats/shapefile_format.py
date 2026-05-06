"""``ShapefileFormat`` — Esri shapefile bundle encoder/decoder.

Shapefile is a multi-file format: a single logical "file" is at minimum
a ``.shp`` (geometry), ``.shx`` (index), and ``.dbf`` (attributes), and
typically also a ``.prj`` (CRS). Pirn :class:`FileFormat` instances work
with a single byte payload, so this implementation expects (and emits)
a ZIP archive containing the component files.

Each record corresponds to one feature::

    {
        "geometry":   list[tuple[float, float]],
        "shape_type": str,
        **attribute_fields,
    }

Round-trip is intrinsically lossy in the shape-type and field-schema
dimensions because pyshp infers ``.dbf`` field widths from the first
record. Tests assert structural and value survival, not byte-equality.

Install: ``pip install pirn[shapefile]``.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class ShapefileFormat(BatchFileFormat):
    """Whole-bundle Esri shapefile encoder/decoder backed by ``pyshp``."""

    @property
    def name(self) -> str:
        return "shapefile"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        shapefile = self._load_pyshp()
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise ValueError("ShapefileFormat: payload is not a valid ZIP archive")
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            shp_bytes = self._read_member(archive, ".shp")
            dbf_bytes = self._read_member(archive, ".dbf")
            shx_bytes = self._read_member(archive, ".shx", optional=True)
        assert shp_bytes is not None
        assert dbf_bytes is not None
        kwargs: dict[str, Any] = {
            "shp": io.BytesIO(shp_bytes),
            "dbf": io.BytesIO(dbf_bytes),
        }
        if shx_bytes is not None:
            kwargs["shx"] = io.BytesIO(shx_bytes)
        reader = shapefile.Reader(**kwargs)
        records: list[Mapping[str, Any]] = []
        try:
            for shape_record in reader.iterShapeRecords():
                shape = shape_record.shape
                attributes = shape_record.record.as_dict()
                record: dict[str, Any] = {
                    "geometry": [(float(x), float(y)) for x, y in shape.points],
                    "shape_type": shape.shapeTypeName,
                }
                for key, value in attributes.items():
                    record[str(key)] = value
                records.append(record)
        finally:
            reader.close()
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        shapefile = self._load_pyshp()
        materialised: list[Mapping[str, Any]] = list(records)
        shp_buf = io.BytesIO()
        shx_buf = io.BytesIO()
        dbf_buf = io.BytesIO()
        writer = shapefile.Writer(shp=shp_buf, shx=shx_buf, dbf=dbf_buf)
        try:
            attribute_keys = self._attribute_keys(materialised)
            for key in attribute_keys:
                writer.field(key, "C", 254)
            for record in materialised:
                self._validate_record(record)
                geometry = record["geometry"]
                if not geometry:
                    raise ValueError(
                        "ShapefileFormat: record geometry must contain at least one coordinate pair"
                    )
                first_point = geometry[0]
                writer.point(float(first_point[0]), float(first_point[1]))
                writer.record(
                    *[self._serialise_attribute(record.get(key)) for key in attribute_keys]
                )
        finally:
            writer.close()
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("layer.shp", shp_buf.getvalue())
            archive.writestr("layer.shx", shx_buf.getvalue())
            archive.writestr("layer.dbf", dbf_buf.getvalue())
        return zip_buf.getvalue()

    @staticmethod
    def _attribute_keys(
        records: list[Mapping[str, Any]],
    ) -> list[str]:
        if not records:
            return []
        keys: list[str] = []
        seen: set[str] = set()
        for key in records[0].keys():
            if key in ("geometry", "shape_type"):
                continue
            if key not in seen:
                keys.append(str(key))
                seen.add(str(key))
        return keys

    @staticmethod
    def _validate_record(record: Mapping[str, Any]) -> None:
        if "geometry" not in record:
            raise ValueError("ShapefileFormat: record missing required 'geometry' field")
        geometry = record["geometry"]
        if not isinstance(geometry, (list, tuple)):
            raise TypeError(
                "ShapefileFormat: geometry must be a list of (x, y) "
                f"tuples, got {type(geometry).__name__}"
            )

    @staticmethod
    def _serialise_attribute(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _read_member(
        archive: zipfile.ZipFile,
        suffix: str,
        optional: bool = False,
    ) -> bytes | None:
        for member in archive.namelist():
            if member.lower().endswith(suffix):
                return archive.read(member)
        if optional:
            return None
        raise ValueError(f"ShapefileFormat: archive is missing required {suffix!r} member")

    @staticmethod
    def _load_pyshp() -> Any:
        try:
            import shapefile
        except ImportError as exc:
            raise ImportError(
                "ShapefileFormat requires pyshp. Install with `pip install pirn[shapefile]`."
            ) from exc
        return shapefile
