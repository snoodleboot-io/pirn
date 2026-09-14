# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
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

Install: ``pip install "pirn-core[safetensors]"``.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, SupportsIndex

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency

if TYPE_CHECKING:
    from numpy.typing import DTypeLike, NDArray


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
        import numpy as np

        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                f"SafetensorsFormat: payload must be bytes, got {type(payload).__name__}"
            )
        safetensors_numpy = OptionalDependency.require("safetensors.numpy", extra="safetensors")
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
                entry["data"] = np.asarray(array).flatten().tolist()
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
        tensors_in: object = record["tensors"]
        if not PayloadShape.is_mapping(tensors_in):
            raise TypeError(
                f"SafetensorsFormat: 'tensors' must be a mapping, got {type(tensors_in).__name__}"
            )
        metadata_in: object = record.get("metadata") or {}
        if not PayloadShape.is_mapping(metadata_in):
            raise TypeError(
                f"SafetensorsFormat: 'metadata' must be a mapping, got {type(metadata_in).__name__}"
            )
        metadata: dict[str, str] = {}
        for key, value in metadata_in.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError(
                    "SafetensorsFormat: metadata keys and values must be "
                    "str (safetensors header restriction); offending pair "
                    f"{key!r}: {value!r}"
                )
            metadata[key] = value
        safetensors_numpy = OptionalDependency.require("safetensors.numpy", extra="safetensors")
        arrays: dict[str, NDArray[Any]] = {}
        for tensor_name, tensor_spec in tensors_in.items():
            if not isinstance(tensor_name, str) or not tensor_name:
                raise ValueError(
                    "SafetensorsFormat: tensor names must be non-empty "
                    f"strings, got {tensor_name!r}"
                )
            arrays[tensor_name] = self._coerce_to_array(tensor_spec)
        try:
            serialised: bytes = safetensors_numpy.save(arrays, metadata=metadata or None)
        except Exception as exc:
            raise ValueError(f"SafetensorsFormat: failed to serialise tensors — {exc}") from exc
        return serialised

    @staticmethod
    def _coerce_to_array(spec: Any) -> NDArray[Any]:
        import numpy as np

        if hasattr(spec, "shape") and hasattr(spec, "dtype"):
            return np.ascontiguousarray(spec)
        if PayloadShape.is_mapping(spec):
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
            if not PayloadShape.is_sequence(shape):
                raise TypeError(
                    "SafetensorsFormat: tensor spec 'shape' must be a list or tuple, "
                    f"got {type(shape).__name__}"
                )
            dims: list[SupportsIndex] = []
            for dim in shape:
                if not isinstance(dim, SupportsIndex):
                    raise TypeError(
                        "SafetensorsFormat: tensor spec 'shape' entries must be "
                        f"integers, got {type(dim).__name__}"
                    )
                dims.append(dim)
            # A ``numpy.dtype`` instance stringifies to its canonical name.
            resolved_dtype: DTypeLike = dtype if isinstance(dtype, (str, type)) else str(dtype)
            array = np.asarray(spec["data"], dtype=resolved_dtype)
            return np.ascontiguousarray(array.reshape(tuple(dims)))
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
            header: object = json.loads(header_text)
        except (UnicodeDecodeError, ValueError):
            return {}
        if not PayloadShape.is_dict(header):
            return {}
        meta = header.get("__metadata__")
        if not PayloadShape.is_dict(meta):
            return {}
        return {str(key): str(value) for key, value in meta.items()}
