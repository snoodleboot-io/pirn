"""``MegObjectStoreAssembler`` — assemble a :class:`HealthSignalPayload` from raw MEG bytes.

Sits between an object store connector (which produces ``bytes``) and downstream
domain knots that consume :class:`~pirn_health.types.health_signal_payload.HealthSignalPayload`.

Algorithm:
    1. Receive ``body`` (raw bytes), ``signal_id``, ``channel_count``, ``sample_rate_hz``,
       and ``samples_per_channel``.
    2. Validate types and values.
    3. Decode the sample array with :class:`MneSampleArrayDecoder` — the same ``.npy``
       buffer :class:`MegObjectStoreDisassembler` writes — and require its shape to be
       ``(channel_count, samples_per_channel)``.
    4. Return a :class:`HealthSignalPayload` carrying the decoded sample array and a
       :class:`HealthSignalFrame` built from the supplied metadata.

References:
    - MNE read_raw_fif: https://mne.tools/stable/generated/mne.io.read_raw_fif.html
    - CTF MEG: https://www.ctf.com/
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.assemblers._mne_sample_array_decoder import MneSampleArrayDecoder
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload


class MegObjectStoreAssembler(Assembler):
    """Assemble a :class:`HealthSignalPayload` from raw MEG bytes stored in an object store."""

    def __init__(
        self,
        *,
        body: Knot,
        signal_id: Knot | str,
        channel_count: Knot | int,
        sample_rate_hz: Knot | float,
        samples_per_channel: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            signal_id=signal_id,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            samples_per_channel=samples_per_channel,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        signal_id: str,
        channel_count: int,
        sample_rate_hz: float,
        samples_per_channel: int,
        **_: Any,
    ) -> HealthSignalPayload:
        """Decode raw MEG bytes into a :class:`HealthSignalPayload`.

        Args:
            body: Raw bytes from an object store, in NumPy ``.npy`` or single-array
                ``.npz`` format.
            signal_id: Non-empty signal identifier string.
            channel_count: Positive integer number of MEG channels.
            sample_rate_hz: Positive sample rate in Hz.
            samples_per_channel: Positive number of samples per channel.

        Returns:
            :class:`HealthSignalPayload` with shape ``(channel_count, samples_per_channel)`` and
            :class:`HealthSignalFrame` metadata.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or a numeric param has wrong type.
            ValueError: If ``signal_id`` is empty, any numeric value is non-positive, or
                ``body`` does not decode to an array of the declared shape.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"MegObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(signal_id, str):
            raise TypeError(
                f"MegObjectStoreAssembler: signal_id must be str, got {type(signal_id).__name__}"
            )
        if not signal_id:
            raise ValueError("MegObjectStoreAssembler: signal_id must be non-empty")
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise ValueError("MegObjectStoreAssembler: channel_count must be a positive int")
        if not isinstance(sample_rate_hz, (int, float)) or float(sample_rate_hz) <= 0.0:
            raise ValueError("MegObjectStoreAssembler: sample_rate_hz must be a positive number")
        if not isinstance(samples_per_channel, int) or samples_per_channel <= 0:
            raise ValueError("MegObjectStoreAssembler: samples_per_channel must be a positive int")
        return await asyncio.to_thread(
            self._assemble_meg,
            body,
            signal_id,
            channel_count,
            float(sample_rate_hz),
            samples_per_channel,
        )

    @staticmethod
    def _assemble_meg(
        body: bytes,
        signal_id: str,
        channel_count: int,
        sample_rate_hz: float,
        samples_per_channel: int,
    ) -> HealthSignalPayload:
        data = MneSampleArrayDecoder.decode(
            body,
            knot_name="MegObjectStoreAssembler",
            channel_count=channel_count,
            samples_per_channel=samples_per_channel,
        )
        frame = HealthSignalFrame(
            signal_id=signal_id,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            samples_per_channel=samples_per_channel,
            fetched_at=datetime.now(UTC),
        )
        return HealthSignalPayload(metadata=frame, data=data)
