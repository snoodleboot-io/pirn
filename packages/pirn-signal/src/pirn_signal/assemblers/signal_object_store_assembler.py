"""``SignalObjectStoreAssembler`` — assemble a :class:`SignalPayload` from raw audio bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream domain knots that consume
:class:`~pirn_signal.types.signal_payload.SignalPayload`.

Algorithm:
    1. Receive ``body`` (raw audio bytes) and ``signal_id``.
    2. Validate types and values.
    3. Decode bytes via ``librosa.load`` on a thread to avoid blocking the event loop.
    4. Return a :class:`SignalPayload` carrying the decoded sample array and a
       :class:`SignalFrame` built from the decoded metadata.

References:
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from typing import Any

import librosa
import numpy as np
from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


def _decode(body: bytes, signal_id: str) -> SignalPayload:
    samples, sample_rate = librosa.load(io.BytesIO(body), sr=None, mono=False)
    if samples.ndim == 1:
        samples = samples[np.newaxis, :]
    frame = SignalFrame(
        signal_id=signal_id,
        channel_count=samples.shape[0],
        sample_rate_hz=float(sample_rate),
        samples_per_channel=samples.shape[1],
        fetched_at=datetime.now(UTC),
    )
    return SignalPayload(metadata=frame, data=samples)


class SignalObjectStoreAssembler(Assembler):
    """Assemble a :class:`SignalPayload` from raw audio bytes.

    Receives bytes from an upstream connector knot (e.g.
    :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`)
    and decodes them into a typed :class:`SignalPayload`. Performs no I/O.
    """

    def __init__(
        self,
        *,
        body: Knot,
        signal_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, signal_id=signal_id, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        signal_id: str,
        **_: Any,
    ) -> SignalPayload:
        """Decode raw audio bytes into a :class:`SignalPayload`.

        Args:
            body: Raw audio bytes from an object store or other connector.
            signal_id: Non-empty identifier for this signal (e.g. file key or tag name).

        Returns:
            :class:`SignalPayload` with sample data decoded from ``body`` and
            a :class:`SignalFrame` populated from the decoded file metadata.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``signal_id`` is not a ``str``.
            ValueError: If ``signal_id`` is empty.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"SignalObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(signal_id, str):
            raise TypeError(
                f"SignalObjectStoreAssembler: signal_id must be str, got {type(signal_id).__name__}"
            )
        if not signal_id:
            raise ValueError("SignalObjectStoreAssembler: signal_id must be non-empty")
        return await asyncio.to_thread(_decode, body, signal_id)
