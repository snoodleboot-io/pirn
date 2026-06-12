"""``AvroFormat`` — Apache Avro batch encoder/decoder.

Uses the ``fastavro`` library. Avro container files include the schema
in their header, so reads do not require a caller-supplied schema.
Writes accept an optional schema; when omitted, a schema is inferred
from the first record's keys and value types.

Avro streaming decode is feasible in principle (the file is a sequence
of blocks), but ``fastavro``'s public reader API expects a complete
file-like object. We expose Avro through :class:`BatchFileFormat` for
that reason; an incremental variant can be added later if a streaming
fastavro API stabilises.

Install: ``pip install pirn[avro]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class AvroFormat(BatchFileFormat):
    """Whole-file Avro encoder/decoder backed by ``fastavro``."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        if schema is not None and not isinstance(schema, dict):
            raise TypeError(
                f"AvroFormat: schema must be a dict or None, got {type(schema).__name__}"
            )
        self._schema = schema

    @property
    def name(self) -> str:
        return "avro"

    @property
    def schema(self) -> dict[str, Any] | None:
        return self._schema

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        fastavro = self._load_fastavro()
        reader = fastavro.reader(io.BytesIO(payload))
        return [dict(record) for record in reader]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        fastavro = self._load_fastavro()
        materialised: list[Mapping[str, Any]] = list(records)
        schema = self._schema
        if schema is None:
            if not materialised:
                raise ValueError(
                    "AvroFormat: cannot infer schema from an empty "
                    "record set; pass schema=... to the constructor"
                )
            schema = self._infer_schema(materialised[0])
        buf = io.BytesIO()
        fastavro.writer(buf, schema, materialised)
        return buf.getvalue()

    @staticmethod
    def _load_fastavro() -> Any:
        try:
            import fastavro
        except ImportError as exc:
            raise ImportError(
                "AvroFormat requires fastavro. Install with `pip install pirn[avro]`."
            ) from exc
        return fastavro

    @classmethod
    def _infer_schema(cls, sample: Mapping[str, Any]) -> dict[str, Any]:
        fields: list[dict[str, Any]] = []
        for key, value in sample.items():
            fields.append(
                {
                    "name": str(key),
                    "type": cls._infer_field_type(value),
                }
            )
        return {
            "type": "record",
            "name": "PirnInferredRecord",
            "fields": fields,
        }

    @staticmethod
    def _infer_field_type(value: Any) -> Any:
        if value is None:
            return ["null", "string"]
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "long"
        if isinstance(value, float):
            return "double"
        if isinstance(value, bytes):
            return "bytes"
        if isinstance(value, str):
            return "string"
        return ["null", "string"]
