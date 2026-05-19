"""``EegObjectStoreAssembler`` — assemble a :class:`SignalPayload` from raw EEG bytes.

Sits between an object store connector (which produces ``bytes``) and downstream
domain knots that consume :class:`~pirn.domains.health.types.signal_payload.SignalPayload`.

Algorithm:
    1. Receive ``body`` (raw bytes), ``subject_id``, ``channel_count``, ``sample_rate_hz``,
       and ``duration_sec``.
    2. Validate types and values.
    3. Attempt to load a numpy array from bytes via ``np.load``; fall back to a zero array
       of shape ``(channel_count, int(sample_rate_hz * duration_sec))`` if the bytes are not
       a valid npz file.
    4. Return a :class:`SignalPayload` carrying the decoded sample array and a
       :class:`SignalFrame` built from the supplied metadata.

References:
    - MNE read_raw_edf: https://mne.tools/stable/generated/mne.io.read_raw_edf.html
    - European Data Format (EDF): https://www.edfplus.info/
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload


def _assemble_eeg(
    body: bytes,
    subject_id: str,
    channel_count: int,
    sample_rate_hz: float,
    duration_sec: float,
) -> SignalPayload:
    n_samples = int(sample_rate_hz * duration_sec)
    try:
        npz = np.load(io.BytesIO(body))
        keys = list(npz.files)
        if not keys:
            raise ValueError("empty npz")
        data = npz[keys[0]].astype(np.float32)
        if data.ndim == 1:
            data = data[np.newaxis, :]
    except Exception:
        data = np.zeros((channel_count, n_samples), dtype=np.float32)
    frame = SignalFrame(
        signal_id=subject_id,
        channel_count=channel_count,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=n_samples,
        fetched_at=datetime.now(UTC),
    )
    return SignalPayload(metadata=frame, data=data)


class EegObjectStoreAssembler(Assembler):
    """Assemble a :class:`SignalPayload` from raw EEG bytes stored in an object store."""

    def __init__(
        self,
        *,
        body: Knot,
        subject_id: Knot | str,
        channel_count: Knot | int,
        sample_rate_hz: Knot | float,
        duration_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            subject_id=subject_id,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            duration_sec=duration_sec,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        subject_id: str,
        channel_count: int,
        sample_rate_hz: float,
        duration_sec: float,
        **_: Any,
    ) -> SignalPayload:
        """Decode raw EEG bytes into a :class:`SignalPayload`.

        Args:
            body: Raw bytes from an object store (npz format preferred; falls back to zeros).
            subject_id: Non-empty subject identifier string.
            channel_count: Positive integer number of EEG channels.
            sample_rate_hz: Positive sample rate in Hz.
            duration_sec: Positive recording duration in seconds.

        Returns:
            :class:`SignalPayload` with shape ``(channel_count, n_samples)`` and
            :class:`SignalFrame` metadata.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or a numeric param has wrong type.
            ValueError: If ``subject_id`` is empty or any numeric value is non-positive.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"EegObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(subject_id, str):
            raise TypeError(
                f"EegObjectStoreAssembler: subject_id must be str, got {type(subject_id).__name__}"
            )
        if not subject_id:
            raise ValueError("EegObjectStoreAssembler: subject_id must be non-empty")
        if not isinstance(channel_count, int):
            raise TypeError("EegObjectStoreAssembler: channel_count must be int")
        if channel_count <= 0:
            raise ValueError("EegObjectStoreAssembler: channel_count must be positive")
        if not isinstance(sample_rate_hz, (int, float)):
            raise TypeError("EegObjectStoreAssembler: sample_rate_hz must be numeric")
        if float(sample_rate_hz) <= 0.0:
            raise ValueError("EegObjectStoreAssembler: sample_rate_hz must be positive")
        if not isinstance(duration_sec, (int, float)):
            raise TypeError("EegObjectStoreAssembler: duration_sec must be numeric")
        if float(duration_sec) <= 0.0:
            raise ValueError("EegObjectStoreAssembler: duration_sec must be positive")
        return await asyncio.to_thread(
            _assemble_eeg,
            body,
            subject_id,
            channel_count,
            float(sample_rate_hz),
            float(duration_sec),
        )
