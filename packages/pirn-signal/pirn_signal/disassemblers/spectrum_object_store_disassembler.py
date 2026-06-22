"""``SpectrumObjectStoreDisassembler`` — serialize a :class:`SpectrumPayload` to raw npz bytes.

Sits between upstream domain knots that produce
:class:`~pirn_signal.types.spectrum_payload.SpectrumPayload` and a
downstream connector sink knot (e.g. an object-store write sink) that
consumes raw ``bytes``. Performs no I/O.

Algorithm:
    1. Receive a :class:`SpectrumPayload` from an upstream knot.
    2. Validate type and non-emptiness.
    3. On a thread, pack the spectral array and frame metadata into npz bytes via ``numpy``.
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

from pirn_signal.types.spectrum_payload import SpectrumPayload


def _encode(payload: SpectrumPayload) -> bytes:
    buf = io.BytesIO()
    arrays: dict[str, np.ndarray] = {
        "data": payload.data,
        "signal_id": np.array(payload.metadata.signal_id),
        "frequency_bins": np.array(payload.metadata.frequency_bins),
        "frequency_resolution_hz": np.array(payload.metadata.frequency_resolution_hz),
    }
    np.savez(buf, **arrays)  # type: ignore[arg-type]
    return buf.getvalue()


class SpectrumObjectStoreDisassembler(Disassembler):
    """Serialize a :class:`SpectrumPayload` to raw npz bytes.

    Receives a typed :class:`SpectrumPayload` from an upstream domain knot and
    packs the spectral array and frame metadata into npz bytes suitable for a
    connector sink. Performs no I/O.
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
        payload: SpectrumPayload,
        **_: Any,
    ) -> bytes:
        """Encode a :class:`SpectrumPayload` into npz bytes.

        Args:
            payload: The spectrum payload to serialize.

        Returns:
            Raw npz bytes containing the spectral array and frame metadata.

        Raises:
            TypeError: If ``payload`` is not a :class:`SpectrumPayload`.
            ValueError: If ``payload.data`` is empty.
        """
        if not isinstance(payload, SpectrumPayload):
            raise TypeError(
                f"SpectrumObjectStoreDisassembler: payload must be SpectrumPayload, got {type(payload).__name__}"
            )
        if payload.data.size == 0:
            raise ValueError("SpectrumObjectStoreDisassembler: payload.data must be non-empty")
        return await asyncio.to_thread(_encode, payload)
