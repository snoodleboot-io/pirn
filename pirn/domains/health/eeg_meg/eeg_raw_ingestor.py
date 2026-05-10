"""``EEGRawIngestor`` — load a raw EEG recording from disk.

Production version uses ``mne.io.read_raw_edf`` /
``mne.io.read_raw_brainvision``. This implementation validates the path,
synthesises a zero-filled sample array of the correct shape, and returns a
:class:`SignalPayload` so downstream knots receive both metadata and data.

Algorithm:
    1. Receive recording_path, subject_id, channel_count, sample_rate_hz, and duration_sec.
    2. Validate types and that numeric values are positive and strings are non-empty.
    3. Synthesise a (channel_count, n_samples) zero array where n_samples = sample_rate_hz * duration_sec.
    4. Return a SignalPayload wrapping the SignalFrame metadata and the data array.


References:
    - MNE read_raw_edf: https://mne.tools/stable/generated/mne.io.read_raw_edf.html
    - European Data Format (EDF): https://www.edfplus.info/
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload


def _load_eeg(
    recording_path: str,
    subject_id: str,
    channel_count: int,
    sample_rate_hz: float,
    duration_sec: float,
) -> SignalPayload:
    n_samples = int(sample_rate_hz * duration_sec)
    data = np.zeros((channel_count, n_samples), dtype=np.float32)
    frame = SignalFrame(
        signal_id=subject_id,
        channel_count=channel_count,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=n_samples,
        fetched_at=datetime.now(UTC),
    )
    return SignalPayload(metadata=frame, data=data)


class EEGRawIngestor(Knot):
    """Load a raw EEG recording into a :class:`SignalPayload`."""

    def __init__(
        self,
        *,
        recording_path: Knot | str,
        subject_id: Knot | str,
        channel_count: Knot | int,
        sample_rate_hz: Knot | float,
        duration_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            recording_path=recording_path,
            subject_id=subject_id,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            duration_sec=duration_sec,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        recording_path: str,
        subject_id: str,
        channel_count: int,
        sample_rate_hz: float,
        duration_sec: float,
        **_: Any,
    ) -> SignalPayload:
        """Load the EEG recording from disk and return a SignalPayload.

        Args:
            recording_path: Non-empty path string to the EEG file.
            subject_id: Non-empty subject identifier string.
            channel_count: Positive integer number of EEG channels.
            sample_rate_hz: Positive sample rate in Hz.
            duration_sec: Positive recording duration in seconds.

        Returns:
            SignalPayload with shape (channel_count, n_samples) and SignalFrame metadata.

        Raises:
            ValueError: If any string is empty or any numeric value is non-positive.
            TypeError: If types are wrong.
        """
        for label, value in (
            ("recording_path", recording_path),
            ("subject_id", subject_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"EEGRawIngestor: {label} must be a non-empty string")
        if not isinstance(channel_count, int):
            raise TypeError("EEGRawIngestor: channel_count must be int")
        if channel_count <= 0:
            raise ValueError("EEGRawIngestor: channel_count must be positive")
        if not isinstance(sample_rate_hz, (int, float)):
            raise TypeError("EEGRawIngestor: sample_rate_hz must be numeric")
        if float(sample_rate_hz) <= 0.0:
            raise ValueError("EEGRawIngestor: sample_rate_hz must be positive")
        if not isinstance(duration_sec, (int, float)):
            raise TypeError("EEGRawIngestor: duration_sec must be numeric")
        if float(duration_sec) <= 0.0:
            raise ValueError("EEGRawIngestor: duration_sec must be positive")
        return await asyncio.to_thread(
            _load_eeg,
            recording_path,
            subject_id,
            channel_count,
            float(sample_rate_hz),
            float(duration_sec),
        )
