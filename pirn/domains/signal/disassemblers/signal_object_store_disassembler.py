"""``SignalObjectStoreDisassembler`` — serialize a :class:`SignalPayload` to raw WAV bytes.

Sits between upstream domain knots that produce
:class:`~pirn.domains.signal.types.signal_payload.SignalPayload` and a
downstream connector sink knot (e.g. an object-store write sink) that
consumes raw ``bytes``. Performs no I/O.

Algorithm:
    1. Receive a :class:`SignalPayload` from an upstream knot.
    2. Validate type and non-emptiness.
    3. On a thread, encode the sample array to WAV bytes via ``soundfile``.
    4. Return the raw WAV bytes.

References:
    - SoundFile: https://python-soundfile.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
import soundfile as sf

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _encode(payload: SignalPayload) -> bytes:
    data: np.ndarray = payload.data
    if data.ndim == 1:
        audio = data
    else:
        audio = data.T
    buf = io.BytesIO()
    sf.write(
        buf, audio, samplerate=int(payload.metadata.sample_rate_hz), format="WAV", subtype="FLOAT"
    )
    return buf.getvalue()


class SignalObjectStoreDisassembler(Disassembler):
    """Serialize a :class:`SignalPayload` to raw WAV bytes.

    Receives a typed :class:`SignalPayload` from an upstream domain knot and
    encodes the sample array into WAV bytes suitable for a connector sink. Performs
    no I/O.
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
        payload: SignalPayload,
        **_: Any,
    ) -> bytes:
        """Encode a :class:`SignalPayload` into WAV bytes.

        Args:
            payload: The signal payload to serialize.

        Returns:
            Raw WAV bytes encoding the sample data at float32 precision.

        Raises:
            TypeError: If ``payload`` is not a :class:`SignalPayload`.
            ValueError: If ``payload.data`` is empty.
        """
        if not isinstance(payload, SignalPayload):
            raise TypeError(
                f"SignalObjectStoreDisassembler: payload must be SignalPayload, got {type(payload).__name__}"
            )
        if payload.data.size == 0:
            raise ValueError("SignalObjectStoreDisassembler: payload.data must be non-empty")
        return await asyncio.to_thread(_encode, payload)
