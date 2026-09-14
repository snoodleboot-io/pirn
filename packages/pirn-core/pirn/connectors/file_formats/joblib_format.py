# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``JoblibFormat`` — joblib-pickled artefact encoder/decoder.

joblib is the de-facto persistence layer for scikit-learn estimators
and other Python objects that benefit from compressed numpy storage.
**joblib uses pickle internally**, which makes
:func:`joblib.load` on attacker-controlled bytes a remote-code-execution
sink.

This module mirrors the trust-boundary contract used by
:class:`pirn.backends.base.cloud_object_store.CloudObjectStore`:
construction REFUSES to proceed without an explicit acknowledgement
that the caller understands the risk. The caller must either pass a
:class:`pirn.backends.signer.Signer` (production) or set
``allow_unsigned=True`` (single-tenant dev / test only).

When a signer is configured, payloads are HMAC-SHA256 signed before
emission and verified before deserialisation; unsigned tampered
payloads cannot reach :func:`joblib.load`.

Like ONNX and safetensors, joblib artefacts are whole-object — each
artefact is one "row".

Install: ``pip install "pirn-core[joblib]"``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency

if TYPE_CHECKING:
    from pirn.backends.signer import Signer


class JoblibFormat(BatchFileFormat):
    """Whole-file joblib (pickle) encoder/decoder with mandatory signer.

    One record is emitted per file::

        {
            "object":       Any,   # the deserialised Python object
            "object_type":  str,   # type(object).__name__
        }

    Encoding accepts the same shape and requires exactly one record
    containing an ``"object"`` key.
    """

    def __init__(
        self,
        signer: Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        if not isinstance(allow_unsigned, bool):
            raise TypeError(
                f"JoblibFormat: allow_unsigned must be a bool, got {type(allow_unsigned).__name__}"
            )
        if signer is None and not allow_unsigned:
            raise ValueError(
                "JoblibFormat: refusing unsigned construction. joblib "
                "uses pickle internally; joblib.load on attacker-"
                "controlled bytes is a remote-code-execution sink. "
                "Pass signer= for production or allow_unsigned=True "
                "for test/dev to acknowledge the trust-boundary "
                "assumption."
            )
        self._signer = signer

    @property
    def name(self) -> str:
        return "joblib"

    @property
    def signed(self) -> bool:
        return self._signer is not None

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"JoblibFormat: payload must be bytes, got {type(payload).__name__}")
        raw = bytes(payload)
        if self._signer is not None:
            raw = self._signer.verify(raw)
        joblib = OptionalDependency.require("joblib", extra="joblib")
        try:
            obj = joblib.load(io.BytesIO(raw))
        except Exception as exc:
            raise ValueError(f"JoblibFormat: failed to deserialise payload — {exc}") from exc
        record: dict[str, Any] = {
            "object": obj,
            "object_type": type(obj).__name__,
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "JoblibFormat: expected exactly one record containing "
                f"'object', got {len(materialised)}"
            )
        record = materialised[0]
        if "object" not in record:
            raise ValueError("JoblibFormat: record missing required 'object' key")
        joblib = OptionalDependency.require("joblib", extra="joblib")
        buf = io.BytesIO()
        try:
            joblib.dump(record["object"], buf)
        except Exception as exc:
            raise ValueError(f"JoblibFormat: failed to serialise object — {exc}") from exc
        payload = buf.getvalue()
        if self._signer is not None:
            payload = self._signer.sign(payload)
        return payload
