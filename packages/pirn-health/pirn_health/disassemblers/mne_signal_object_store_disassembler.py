"""``MneSignalObjectStoreDisassembler`` — shared bytes serialisation for MNE-backed signal disassemblers.

:class:`~pirn_health.disassemblers.eeg_object_store_disassembler.EegObjectStoreDisassembler`
and :class:`~pirn_health.disassemblers.meg_object_store_disassembler.MegObjectStoreDisassembler`
were identical modulo their public name and docstrings — both serialise a
:class:`~pirn_health.types.health_signal_payload.HealthSignalPayload` produced
by an MNE-backed acquisition knot (EEG or MEG) to raw bytes. This shared base
holds the one real implementation; the public classes are thin subclasses
that exist to give each modality its own discoverable name.

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

from pirn_health.types.health_signal_payload import HealthSignalPayload


class MneSignalObjectStoreDisassembler(Disassembler):
    """Shared implementation for EEG/MEG object-store disassemblers."""

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
        """Serialise the sample array to bytes.

        Args:
            payload: :class:`HealthSignalPayload` produced by an upstream MNE-backed knot.

        Returns:
            Raw ``bytes`` of the sample array in NumPy ``.npy`` format.

        Raises:
            TypeError: If ``payload`` is not a :class:`HealthSignalPayload`.
        """
        if not isinstance(payload, HealthSignalPayload):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError(
                f"{type(self).__name__}: payload must be HealthSignalPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(self._serialise, payload)

    @staticmethod
    def _serialise(payload: HealthSignalPayload) -> bytes:
        buf = io.BytesIO()
        np.save(buf, payload.data)
        return buf.getvalue()
