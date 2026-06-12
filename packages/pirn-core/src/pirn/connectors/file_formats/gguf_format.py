"""``GgufFormat`` — GGUF (llama.cpp quantised LLM weight) encoder/decoder.

GGUF is the binary container used by ``llama.cpp`` for quantised LLM
weights. The format places its tensor index at a known offset, but the
``gguf`` Python package only exposes a buffered reader API: payloads
are decoded in full rather than streamed.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record exposing the GGUF
header and tensor metadata; :meth:`_encode_full` accepts the same
shape and serialises via ``gguf.GGUFWriter``.

Security: pirn does not sandbox ``gguf``. Malformed payloads may trigger
upstream library bugs — the parser is generally robust but treat
untrusted payloads accordingly.

Install: ``pip install pirn[gguf]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class GgufFormat(BatchFileFormat):
    """Whole-file GGUF encoder/decoder."""

    def __init__(self) -> None:
        return

    @property
    def name(self) -> str:
        return "gguf"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"GgufFormat: payload must be bytes, got {type(payload).__name__}")
        gguf = self._load_gguf()
        # ``GGUFReader`` accepts a path or an open file handle. To avoid
        # disk IO when callers hand us bytes, materialise a temp file.
        with tempfile.NamedTemporaryFile(
            prefix="pirn-gguf-", suffix=".gguf", delete=False
        ) as handle:
            handle.write(bytes(payload))
            tmp_path = handle.name
        try:
            try:
                reader = gguf.GGUFReader(tmp_path)
            except Exception as exc:
                raise ValueError(f"GgufFormat: failed to parse GGUF payload — {exc}") from exc
            metadata: dict[str, Any] = {}
            fields = getattr(reader, "fields", {}) or {}
            for key, field in fields.items():
                metadata[str(key)] = self._field_value(field)
            tensors = getattr(reader, "tensors", []) or []
            tensor_names = [str(getattr(t, "name", "")) for t in tensors]
            version_value = metadata.get("GGUF.version") or metadata.get("general.version")
            try:
                version = int(version_value) if version_value is not None else 0
            except (TypeError, ValueError):
                version = 0
            record: dict[str, Any] = {
                "version": version,
                "tensor_count": len(tensor_names),
                "metadata": metadata,
                "tensor_names": tensor_names,
            }
            return [record]
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(f"GgufFormat: expected exactly one record, got {len(materialised)}")
        record = materialised[0]
        for key in ("metadata", "tensors", "architecture"):
            if key not in record:
                raise ValueError(
                    f"GgufFormat: record missing required {key!r} key "
                    "(metadata: Mapping, tensors: Sequence of "
                    "{name, data, dtype}, architecture: str)"
                )
        architecture = record["architecture"]
        if not isinstance(architecture, str) or not architecture:
            raise ValueError(
                f"GgufFormat: 'architecture' must be a non-empty string, got {architecture!r}"
            )
        metadata = record["metadata"]
        if not isinstance(metadata, Mapping):
            raise TypeError(
                f"GgufFormat: 'metadata' must be a Mapping, got {type(metadata).__name__}"
            )
        tensors = record["tensors"]
        if not isinstance(tensors, Iterable):
            raise TypeError(f"GgufFormat: 'tensors' must be iterable, got {type(tensors).__name__}")
        gguf = self._load_gguf()
        with tempfile.NamedTemporaryFile(
            prefix="pirn-gguf-write-", suffix=".gguf", delete=False
        ) as handle:
            tmp_path = handle.name
        try:
            writer = gguf.GGUFWriter(tmp_path, architecture)
            try:
                for key, value in metadata.items():
                    if not isinstance(key, str):
                        raise TypeError(
                            f"GgufFormat: metadata keys must be str, got {type(key).__name__}"
                        )
                    self._write_metadata_value(writer, key, value)
                for tensor in tensors:
                    if not isinstance(tensor, Mapping):
                        raise TypeError(
                            "GgufFormat: each tensor must be a Mapping with 'name' and 'data' keys"
                        )
                    name = tensor.get("name")
                    data = tensor.get("data")
                    if not isinstance(name, str) or not name:
                        raise ValueError("GgufFormat: tensor 'name' must be a non-empty string")
                    if data is None:
                        raise ValueError("GgufFormat: tensor 'data' is required")
                    writer.add_tensor(name, data)
                writer.write_header_to_file()
                writer.write_kv_data_to_file()
                writer.write_tensors_to_file()
            finally:
                writer.close()
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _field_value(field: Any) -> Any:
        # ``ReaderField.contents()`` is the canonical accessor in modern
        # ``gguf`` releases; older releases exposed ``parts`` directly.
        contents = getattr(field, "contents", None)
        if callable(contents):
            try:
                return contents()
            except (RuntimeError, TypeError, ValueError):
                pass
        for attr in ("value", "parts"):
            value = getattr(field, attr, None)
            if value is not None:
                try:
                    return value.tolist()  # type: ignore[union-attr]
                except AttributeError:
                    return value
        return None

    @staticmethod
    def _write_metadata_value(writer: Any, key: str, value: Any) -> None:
        if isinstance(value, bool):
            writer.add_bool(key, value)
        elif isinstance(value, int):
            writer.add_uint32(key, value)
        elif isinstance(value, float):
            writer.add_float32(key, value)
        elif isinstance(value, str):
            writer.add_string(key, value)
        else:
            raise TypeError(
                f"GgufFormat: unsupported metadata value type for {key!r}: {type(value).__name__}"
            )

    @staticmethod
    def _load_gguf() -> Any:
        try:
            import gguf
        except ImportError as exc:
            raise ImportError(
                "GgufFormat requires gguf. Install with `pip install pirn[gguf]`."
            ) from exc
        return gguf
