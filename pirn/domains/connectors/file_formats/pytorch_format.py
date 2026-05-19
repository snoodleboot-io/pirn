"""``PytorchFormat`` — PyTorch state-dict / model encoder/decoder.

PyTorch artefacts are whole-model pickles (``torch.save`` / ``torch.load``).
They cannot be streamed record-by-record: the archive must be parsed in
full before its tensor / metadata structure is observable.

ML artefacts do not fit the row-of-data model — each artefact is one
"row". :meth:`_decode_full` yields a single record exposing the
deserialised state alongside metadata; :meth:`_encode_full` accepts the
same shape and serialises via ``torch.save``.

Security: ``torch.load`` with ``weights_only=False`` deserialises
arbitrary Python objects via ``pickle`` — this is RCE-prone. The
constructor defaults ``weights_only=True`` (PyTorch's safe-mode loader,
which only restores tensor data and refuses arbitrary callables). Users
who need full model loading must supply a :class:`_Signer` so the
payload is HMAC-verified before deserialisation, or set
``allow_unsigned=True`` to opt out (NOT recommended for untrusted
inputs).

When a signer is configured the encoder prepends a 32-byte HMAC-SHA256
signature; the decoder verifies the signature before invoking
``torch.load``.

Install: ``pip install pirn[pytorch]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.backends._signer import _Signer
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class PytorchFormat(BatchFileFormat):
    """Whole-file PyTorch encoder/decoder.

    One record is emitted per file::

        {
            "state_dict":  Any,   # the object returned by torch.load
            "metadata": {
                "weights_only":  bool,  # whether safe-mode loading was used
                "signed":        bool,  # whether the payload was HMAC-verified
            },
        }

    Encoding accepts the same shape and requires exactly one record
    containing a ``"state_dict"`` key.
    """

    def __init__(
        self,
        weights_only: bool = True,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        if not isinstance(weights_only, bool):
            raise TypeError(
                f"PytorchFormat: weights_only must be a bool, got {type(weights_only).__name__}"
            )
        if signer is not None and not isinstance(signer, _Signer):
            raise TypeError(
                f"PytorchFormat: signer must be a _Signer or None, got {type(signer).__name__}"
            )
        if not isinstance(allow_unsigned, bool):
            raise TypeError(
                f"PytorchFormat: allow_unsigned must be a bool, got {type(allow_unsigned).__name__}"
            )
        if not weights_only and signer is None and not allow_unsigned:
            raise ValueError(
                "PytorchFormat: weights_only=False is RCE-prone — "
                "supply a signer to authenticate payloads, or set "
                "allow_unsigned=True to acknowledge the risk "
                "(strongly discouraged for untrusted inputs)."
            )
        self._weights_only = weights_only
        self._signer = signer
        self._allow_unsigned = allow_unsigned

    @property
    def name(self) -> str:
        return "pytorch"

    @property
    def weights_only(self) -> bool:
        return self._weights_only

    @property
    def signer(self) -> _Signer | None:
        return self._signer

    @property
    def allow_unsigned(self) -> bool:
        return self._allow_unsigned

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"PytorchFormat: payload must be bytes, got {type(payload).__name__}")
        raw = bytes(payload)
        if self._signer is not None:
            raw = self._signer.verify(raw)
        torch = self._load_torch()
        try:
            state = torch.load(io.BytesIO(raw), weights_only=self._weights_only)
        except Exception as exc:
            raise ValueError(f"PytorchFormat: failed to deserialise payload — {exc}") from exc
        record: dict[str, Any] = {
            "state_dict": state,
            "metadata": {
                "weights_only": self._weights_only,
                "signed": self._signer is not None,
            },
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised: list[Mapping[str, Any]] = list(records)
        if len(materialised) != 1:
            raise ValueError(
                "PytorchFormat: expected exactly one record containing "
                f"'state_dict', got {len(materialised)}"
            )
        record = materialised[0]
        if "state_dict" not in record:
            raise ValueError("PytorchFormat: record missing required 'state_dict' key")
        state = record["state_dict"]
        torch = self._load_torch()
        buffer = io.BytesIO()
        try:
            torch.save(state, buffer)
        except Exception as exc:
            raise ValueError(f"PytorchFormat: failed to serialise state_dict — {exc}") from exc
        raw = buffer.getvalue()
        if self._signer is not None:
            raw = self._signer.sign(raw)
        return raw

    @staticmethod
    def _load_torch() -> Any:
        try:
            import torch
        except ImportError as exc:
            raise ImportError(
                "PytorchFormat requires torch. Install with `pip install pirn[pytorch]`."
            ) from exc
        return torch
