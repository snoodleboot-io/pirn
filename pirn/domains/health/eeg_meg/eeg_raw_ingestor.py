"""``EEGRawIngestor`` — load a raw EEG recording from disk.

Production version uses ``mne.io.read_raw_edf`` /
``mne.io.read_raw_brainvision``. This stub validates the path and
returns a :class:`RawEEG` summary derived from configuration.

Algorithm:
    1. Receive recording_path, subject_id, channel_count, sample_rate_hz, and duration_sec.
    2. Validate types and that numeric values are positive and strings are non-empty.
    3. Open the EEG file at recording_path and read the header.
    4. Construct a RawEEG from the metadata.
    5. Return the RawEEG summary.


References:
    - MNE read_raw_edf: https://mne.tools/stable/generated/mne.io.read_raw_edf.html
    - European Data Format (EDF): https://www.edfplus.info/
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.raw_eeg import RawEEG


class EEGRawIngestor(Knot):
    """Load a raw EEG recording into a :class:`RawEEG` summary."""

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
    ) -> RawEEG:
        """Load the EEG recording from disk and return a RawEEG summary.

        Args:
            recording_path: Non-empty path string to the EEG file.
            subject_id: Non-empty subject identifier string.
            channel_count: Positive integer number of EEG channels.
            sample_rate_hz: Positive sample rate in Hz.
            duration_sec: Positive recording duration in seconds.

        Returns:
            A RawEEG containing channel count, sample rate, duration, and ingest timestamp.

        Raises:
            ValueError: If any string is empty or any numeric value is non-positive.
            TypeError: If types are wrong.
        """
        for label, value in (
            ("recording_path", recording_path),
            ("subject_id", subject_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"EEGRawIngestor: {label} must be a non-empty string"
                )
        if not isinstance(channel_count, int):
            raise TypeError("EEGRawIngestor: channel_count must be int")
        if channel_count <= 0:
            raise ValueError(
                "EEGRawIngestor: channel_count must be positive"
            )
        if not isinstance(sample_rate_hz, (int, float)):
            raise TypeError(
                "EEGRawIngestor: sample_rate_hz must be numeric"
            )
        if float(sample_rate_hz) <= 0.0:
            raise ValueError(
                "EEGRawIngestor: sample_rate_hz must be positive"
            )
        if not isinstance(duration_sec, (int, float)):
            raise TypeError("EEGRawIngestor: duration_sec must be numeric")
        if float(duration_sec) <= 0.0:
            raise ValueError(
                "EEGRawIngestor: duration_sec must be positive"
            )
        return RawEEG(
            subject_id=subject_id,
            channel_count=channel_count,
            sample_rate_hz=float(sample_rate_hz),
            duration_sec=float(duration_sec),
            fetched_at=datetime.now(timezone.utc),
        )
