"""``EegObjectStoreDisassembler`` — disassemble a :class:`HealthSignalPayload` into bytes.

Sits between domain knots that produce :class:`~pirn.domains.health.types.health_signal_payload.HealthSignalPayload`
and an object store sink connector that expects raw ``bytes``.

Algorithm:
    1. Receive a :class:`HealthSignalPayload`.
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
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload


def _serialise(payload: HealthSignalPayload) -> bytes:
    buf = io.BytesIO()
    np.save(buf, payload.data)
    return buf.getvalue()


class EegObjectStoreDisassembler(Disassembler):
    """Disassemble a :class:`HealthSignalPayload` into raw bytes for object store upload."""

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
        payload: HealthSignalPayload,
        **_: Any,
    ) -> bytes:
        """Serialise the EEG sample array to bytes.

        Args:
            payload: :class:`HealthSignalPayload` produced by an upstream EEG knot.

        Returns:
            Raw ``bytes`` of the sample array in NumPy ``.npy`` format.

        Raises:
            TypeError: If ``payload`` is not a :class:`HealthSignalPayload`.
        """
        if not isinstance(payload, HealthSignalPayload):
            raise TypeError(
                f"EegObjectStoreDisassembler: payload must be HealthSignalPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_serialise, payload)
