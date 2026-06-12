"""``OnnxFormat`` — ONNX (Open Neural Network Exchange) model encoder/decoder.

ONNX artefacts are whole-model protobufs. They cannot be streamed
record-by-record: the protobuf must be parsed in full before its graph
metadata (inputs, outputs, opset, producer, node graph) is observable.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record exposing the model
bytes alongside summary metadata; :meth:`_encode_full` accepts the same
shape and validates that the supplied bytes parse as an ONNX model
before emission.

Validation: when ``validate=True`` (default), reads run
``onnx.checker.check_model`` so malformed graphs raise rather than
silently propagate downstream.

Security: pirn does not sandbox ``onnx``. The protobuf parser is
generally robust, but malformed payloads may still trigger upstream
library bugs. Treat untrusted payloads accordingly.

Install: ``pip install pirn[onnx]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class OnnxFormat(BatchFileFormat):
    """Whole-file ONNX model encoder/decoder."""

    def __init__(self, validate: bool = True) -> None:
        if not isinstance(validate, bool):
            raise TypeError(f"OnnxFormat: validate must be a bool, got {type(validate).__name__}")
        self._validate = validate

    @property
    def name(self) -> str:
        return "onnx"

    @property
    def validate(self) -> bool:
        return self._validate

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"OnnxFormat: payload must be bytes, got {type(payload).__name__}")
        onnx = self._load_onnx()
        try:
            model = onnx.load_model_from_string(bytes(payload))
        except Exception as exc:
            raise ValueError(f"OnnxFormat: failed to parse ONNX payload — {exc}") from exc
        if self._validate:
            try:
                onnx.checker.check_model(model)
            except Exception as exc:
                raise ValueError(f"OnnxFormat: ONNX checker rejected model — {exc}") from exc
        graph = model.graph
        record: dict[str, Any] = {
            "model_bytes": bytes(payload),
            "ir_version": int(model.ir_version),
            "producer_name": str(model.producer_name),
            "graph_inputs": [str(value.name) for value in graph.input],
            "graph_outputs": [str(value.name) for value in graph.output],
            "node_count": len(graph.node),
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "OnnxFormat: expected exactly one record containing "
                f"'model_bytes', got {len(materialised)}"
            )
        record = materialised[0]
        if "model_bytes" not in record:
            raise ValueError("OnnxFormat: record missing required 'model_bytes' key")
        payload = record["model_bytes"]
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                f"OnnxFormat: 'model_bytes' must be bytes, got {type(payload).__name__}"
            )
        payload_bytes = bytes(payload)
        onnx = self._load_onnx()
        try:
            onnx.load_model_from_string(payload_bytes)
        except Exception as exc:
            raise ValueError(
                f"OnnxFormat: 'model_bytes' is not a valid ONNX model — {exc}"
            ) from exc
        return payload_bytes

    @staticmethod
    def _load_onnx() -> Any:
        try:
            import onnx
        except ImportError as exc:
            raise ImportError(
                "OnnxFormat requires onnx. Install with `pip install pirn[onnx]`."
            ) from exc
        return onnx
