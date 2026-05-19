"""``MegObjectStoreDisassembler`` — disassemble a :class:`SignalPayload` into bytes.

Sits between domain knots that produce :class:`~pirn.domains.health.types.signal_payload.SignalPayload`
and an object store sink connector that expects raw ``bytes``.

Algorithm:
    1. Receive a :class:`SignalPayload`.
    2. Validate the payload type.
    3. Serialise ``payload.data`` via ``np.save`` into a BytesIO buffer on a thread.
    4. Return the resulting ``bytes``.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _serialise(payload: SignalPayload) -> bytes:
    buf = io.BytesIO()
    np.save(buf, payload.data)
    return buf.getvalue()


class MegObjectStoreDisassembler(Disassembler):
    """Disassemble a :class:`SignalPayload` into raw bytes for object store upload."""

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
        """Serialise the MEG sample array to bytes.

        Args:
            payload: :class:`SignalPayload` produced by an upstream MEG knot.

        Returns:
            Raw ``bytes`` of the sample array in NumPy ``.npy`` format.

        Raises:
            TypeError: If ``payload`` is not a :class:`SignalPayload`.
        """
        if not isinstance(payload, SignalPayload):
            raise TypeError(
                f"MegObjectStoreDisassembler: payload must be SignalPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_serialise, payload)
