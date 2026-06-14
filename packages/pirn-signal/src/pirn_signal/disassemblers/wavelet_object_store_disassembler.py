"""``WaveletObjectStoreDisassembler`` — serialize a :class:`WaveletPayload` to raw npz bytes.

Sits between upstream domain knots that produce
:class:`~pirn_signal.types.wavelet_payload.WaveletPayload` and a
downstream connector sink knot (e.g. an object-store write sink) that
consumes raw ``bytes``. Performs no I/O.

Algorithm:
    1. Receive a :class:`WaveletPayload` from an upstream knot.
    2. Validate type and non-emptiness.
    3. On a thread, pack each decomposition level array and frame metadata into npz bytes via ``numpy``.
    4. Return the raw npz bytes.

References:
    - NumPy savez: https://numpy.org/doc/stable/reference/generated/numpy.savez.html
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.wavelet_payload import WaveletPayload


def _encode(payload: WaveletPayload) -> bytes:
    buf = io.BytesIO()
    arrays: dict[str, np.ndarray] = {f"level_{i}": arr for i, arr in enumerate(payload.data)}
    arrays["signal_id"] = np.array(payload.metadata.signal_id)
    arrays["wavelet_name"] = np.array(payload.metadata.wavelet_name)
    arrays["scale_count"] = np.array(payload.metadata.scale_count)
    np.savez(buf, **arrays)  # type: ignore[arg-type]
    return buf.getvalue()


class WaveletObjectStoreDisassembler(Disassembler):
    """Serialize a :class:`WaveletPayload` to raw npz bytes.

    Receives a typed :class:`WaveletPayload` from an upstream domain knot and
    packs each decomposition level array and frame metadata into npz bytes suitable
    for a connector sink. Performs no I/O.
    """

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(
        self,
        payload: WaveletPayload,
        **_: Any,
    ) -> bytes:
        """Encode a :class:`WaveletPayload` into npz bytes.

        Args:
            payload: The wavelet payload to serialize.

        Returns:
            Raw npz bytes containing per-level decomposition arrays and frame metadata.

        Raises:
            TypeError: If ``payload`` is not a :class:`WaveletPayload`.
            ValueError: If ``payload.data`` contains no decomposition levels.
        """
        if not isinstance(payload, WaveletPayload):
            raise TypeError(
                f"WaveletObjectStoreDisassembler: payload must be WaveletPayload, got {type(payload).__name__}"
            )
        if len(payload.data) == 0:
            raise ValueError(
                "WaveletObjectStoreDisassembler: payload.data must contain at least one decomposition level"
            )
        return await asyncio.to_thread(_encode, payload)
