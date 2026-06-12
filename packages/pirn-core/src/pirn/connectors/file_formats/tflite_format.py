"""``TfliteFormat`` — TensorFlow Lite (FlatBuffer) model encoder/decoder.

TFLite artefacts are FlatBuffer-encoded model containers used for
on-device inference. They cannot be streamed record-by-record: the
buffer must be parsed in full before inputs / outputs / ops are
observable.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record with the original
model bytes alongside input/output tensor metadata extracted via
``ai_edge_litert.interpreter.Interpreter`` (Google's official TFLite
successor), falling back to the legacy ``tflite_runtime`` package and
finally ``tensorflow.lite.Interpreter``.

:meth:`_encode_full` accepts ``model_bytes`` (already a TFLite
FlatBuffer) and emits them verbatim. Building a TFLite model from
source — e.g. via ``tf.lite.TFLiteConverter`` — is out of scope: the
encoder simply round-trips the bytes the caller supplied.

Security: pirn does not sandbox the interpreter. Malicious TFLite models
may contain arbitrary custom ops; treat untrusted payloads accordingly.

Install: ``pip install pirn[tflite]`` (or fall back to ``pirn[tensorflow]``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class TfliteFormat(BatchFileFormat):
    """Whole-file TFLite encoder/decoder."""

    def __init__(self) -> None:
        return

    @property
    def name(self) -> str:
        return "tflite"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"TfliteFormat: payload must be bytes, got {type(payload).__name__}")
        raw = bytes(payload)
        interpreter_cls = self._load_interpreter()
        try:
            interpreter = interpreter_cls(model_content=raw)
            interpreter.allocate_tensors()
        except Exception as exc:
            raise ValueError(f"TfliteFormat: failed to load TFLite payload — {exc}") from exc
        input_details = [self._normalise_details(d) for d in interpreter.get_input_details()]
        output_details = [self._normalise_details(d) for d in interpreter.get_output_details()]
        version = self._extract_version(raw)
        record: dict[str, Any] = {
            "model_bytes": raw,
            "input_details": input_details,
            "output_details": output_details,
            "version": version,
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "TfliteFormat: expected exactly one record containing "
                f"'model_bytes', got {len(materialised)}"
            )
        record = materialised[0]
        if "model_bytes" not in record:
            raise ValueError("TfliteFormat: record missing required 'model_bytes' key")
        model_bytes = record["model_bytes"]
        if not isinstance(model_bytes, (bytes, bytearray)):
            raise TypeError(
                f"TfliteFormat: 'model_bytes' must be bytes, got {type(model_bytes).__name__}"
            )
        return bytes(model_bytes)

    @staticmethod
    def _normalise_details(details: Mapping[str, Any]) -> Mapping[str, Any]:
        # ``Interpreter.get_input_details`` returns dicts containing
        # numpy arrays for shape and dtype objects. Convert to plain
        # Python so records survive serialisation across processes.
        normalised: dict[str, Any] = {}
        for key, value in details.items():
            tolist = getattr(value, "tolist", None)
            if callable(tolist) and not isinstance(value, type):
                normalised[str(key)] = tolist()
            elif hasattr(value, "__name__"):
                normalised[str(key)] = value.__name__
            else:
                normalised[str(key)] = value
        return normalised

    @staticmethod
    def _extract_version(payload: bytes) -> int:
        # The TFLite FlatBuffer schema places the version in the root
        # table. Parsing flatbuffers properly requires the schema; for
        # metadata purposes we expose the file identifier instead — a
        # constant ``"TFL3"`` for the current schema.
        if len(payload) >= 8 and payload[4:8] == b"TFL3":
            return 3
        return 0

    @staticmethod
    def _load_interpreter() -> Any:
        try:
            from ai_edge_litert.interpreter import Interpreter

            return Interpreter
        except ImportError:
            pass
        try:
            from tflite_runtime.interpreter import Interpreter

            return Interpreter
        except ImportError:
            pass
        try:
            from tensorflow.lite import Interpreter as TfInterpreter  # type: ignore[attr-defined]

            return TfInterpreter
        except ImportError as exc:
            raise ImportError(
                "TfliteFormat requires ai-edge-litert, tflite_runtime, or tensorflow. "
                "Install with `pip install pirn[tflite]` or "
                "`pip install pirn[tensorflow]`."
            ) from exc
