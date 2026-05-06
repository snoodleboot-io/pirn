"""``JoblibFormat`` — joblib-pickled artefact encoder/decoder.

joblib is the de-facto persistence layer for scikit-learn estimators
and other Python objects that benefit from compressed numpy storage.
**joblib uses pickle internally**, which makes
:func:`joblib.load` on attacker-controlled bytes a remote-code-execution
sink.

This module mirrors the trust-boundary contract used by
:class:`pirn.backends.base._cloud_object_store._CloudObjectStore`:
construction REFUSES to proceed without an explicit acknowledgement
that the caller understands the risk. The caller must either pass a
:class:`pirn.backends._signer._Signer` (production) or set
``allow_unsigned=True`` (single-tenant dev / test only).

When a signer is configured, payloads are HMAC-SHA256 signed before
emission and verified before deserialisation; unsigned tampered
payloads cannot reach :func:`joblib.load`.

Like ONNX and safetensors, joblib artefacts are whole-object — each
artefact is one "row".

Install: ``pip install pirn[joblib]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)

if TYPE_CHECKING:
    from pirn.backends._signer import _Signer


class JoblibFormat(BatchFileFormat):
    """Whole-file joblib (pickle) encoder/decoder with mandatory signer."""

    def __init__(
        self,
        signer: _Signer | None = None,
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
        joblib = self._load_joblib()
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
        joblib = self._load_joblib()
        buf = io.BytesIO()
        try:
            joblib.dump(record["object"], buf)
        except Exception as exc:
            raise ValueError(f"JoblibFormat: failed to serialise object — {exc}") from exc
        payload = buf.getvalue()
        if self._signer is not None:
            payload = self._signer.sign(payload)
        return payload

    @staticmethod
    def _load_joblib() -> Any:
        try:
            import joblib
        except ImportError as exc:
            raise ImportError(
                "JoblibFormat requires joblib. Install with `pip install pirn[joblib]`."
            ) from exc
        return joblib
