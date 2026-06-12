"""``SafetensorsFormat`` — Hugging Face safetensors encoder/decoder.

Safetensors stores tensor weights in a flat header + payload layout
that is RCE-safe by design: there is no embedded code path during
deserialisation, unlike pickle/joblib. No signer is required.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record exposing the
tensors and file-level metadata; :meth:`_encode_full` accepts the same
shape and serialises via :func:`safetensors.numpy.save`.

Tensor data: when ``include_data=True`` (default), tensor bytes are
materialised as a flat ``list`` for round-trip equality. For very
large models, callers can construct with ``include_data=False`` to
emit only ``shape`` and ``dtype`` per tensor; the read path will then
omit the ``data`` key.

Install: ``pip install pirn[safetensors]``.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class SafetensorsFormat(BatchFileFormat):
    """Whole-file safetensors encoder/decoder."""

    def __init__(self, include_data: bool = True) -> None:
        if not isinstance(include_data, bool):
            raise TypeError(
                f"SafetensorsFormat: include_data must be a bool, got {type(include_data).__name__}"
            )
        self._include_data = include_data

    @property
    def name(self) -> str:
        return "safetensors"

    @property
    def include_data(self) -> bool:
        return self._include_data

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                f"SafetensorsFormat: payload must be bytes, got {type(payload).__name__}"
            )
        numpy_module = self._load_numpy()
        safetensors_numpy = self._load_safetensors_numpy()
        try:
            tensors_array: Mapping[str, Any] = safetensors_numpy.load(bytes(payload))
        except Exception as exc:
            raise ValueError(
                f"SafetensorsFormat: failed to parse safetensors payload — {exc}"
            ) from exc
        metadata = self._extract_metadata(bytes(payload))
        tensors_record: dict[str, dict[str, Any]] = {}
        for name, array in tensors_array.items():
            entry: dict[str, Any] = {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
            }
            if self._include_data:
                entry["data"] = numpy_module.asarray(array).flatten().tolist()
            tensors_record[name] = entry
        record: dict[str, Any] = {
            "tensors": tensors_record,
            "metadata": metadata,
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "SafetensorsFormat: expected exactly one record containing "
                f"'tensors' and 'metadata', got {len(materialised)}"
            )
        record = materialised[0]
        if "tensors" not in record:
            raise ValueError("SafetensorsFormat: record missing required 'tensors' key")
        tensors_in = record["tensors"]
        if not isinstance(tensors_in, Mapping):
            raise TypeError(
                f"SafetensorsFormat: 'tensors' must be a mapping, got {type(tensors_in).__name__}"
            )
        metadata = record.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise TypeError(
                f"SafetensorsFormat: 'metadata' must be a mapping, got {type(metadata).__name__}"
            )
        for key, value in metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError(
                    "SafetensorsFormat: metadata keys and values must be "
                    "str (safetensors header restriction); offending pair "
                    f"{key!r}: {value!r}"
                )
        numpy_module = self._load_numpy()
        safetensors_numpy = self._load_safetensors_numpy()
        arrays: dict[str, Any] = {}
        for tensor_name, tensor_spec in tensors_in.items():
            if not isinstance(tensor_name, str) or not tensor_name:
                raise ValueError(
                    "SafetensorsFormat: tensor names must be non-empty "
                    f"strings, got {tensor_name!r}"
                )
            arrays[tensor_name] = self._coerce_to_array(tensor_spec, numpy_module)
        try:
            return safetensors_numpy.save(arrays, metadata=dict(metadata) if metadata else None)
        except Exception as exc:
            raise ValueError(f"SafetensorsFormat: failed to serialise tensors — {exc}") from exc

    @staticmethod
    def _coerce_to_array(spec: Any, numpy_module: Any) -> Any:
        if hasattr(spec, "shape") and hasattr(spec, "dtype"):
            return numpy_module.ascontiguousarray(spec)
        if isinstance(spec, Mapping):
            if "data" not in spec:
                raise ValueError(
                    "SafetensorsFormat: tensor spec requires 'data' "
                    "(flat list) when include_data is used for encoding"
                )
            shape = spec.get("shape")
            dtype = spec.get("dtype")
            if shape is None or dtype is None:
                raise ValueError(
                    "SafetensorsFormat: tensor spec requires 'shape' and 'dtype' fields"
                )
            array = numpy_module.asarray(spec["data"], dtype=dtype)
            return numpy_module.ascontiguousarray(array.reshape(tuple(shape)))
        raise TypeError(
            "SafetensorsFormat: tensor entries must be a numpy array "
            "or a mapping with 'data', 'shape', 'dtype'; "
            f"got {type(spec).__name__}"
        )

    @staticmethod
    def _extract_metadata(payload: bytes) -> Mapping[str, str]:
        # Header layout: u64 little-endian header length + JSON header bytes.
        if len(payload) < 8:
            return {}
        (header_length,) = struct.unpack("<Q", payload[:8])
        if header_length == 0 or 8 + header_length > len(payload):
            return {}
        try:
            header_text = payload[8 : 8 + header_length].decode("utf-8")
            header = json.loads(header_text)
        except (UnicodeDecodeError, ValueError):
            return {}
        meta = header.get("__metadata__") if isinstance(header, dict) else None
        if not isinstance(meta, dict):
            return {}
        return {str(key): str(value) for key, value in meta.items()}

    @staticmethod
    def _load_safetensors_numpy() -> Any:
        try:
            from safetensors import numpy as safetensors_numpy
        except ImportError as exc:
            raise ImportError(
                "SafetensorsFormat requires safetensors. Install with "
                "`pip install pirn[safetensors]`."
            ) from exc
        return safetensors_numpy

    @staticmethod
    def _load_numpy() -> Any:
        try:
            import numpy
        except ImportError as exc:
            raise ImportError(
                "SafetensorsFormat requires numpy (transitive via "
                "safetensors). Install with "
                "`pip install pirn[safetensors]`."
            ) from exc
        return numpy
