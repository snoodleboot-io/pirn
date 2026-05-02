"""``EEGRawIngestor`` — load a raw EEG recording from disk.

Production version uses ``mne.io.read_raw_edf`` /
``mne.io.read_raw_brainvision``. This stub validates the path and
returns a :class:`RawEEG` summary derived from configuration.
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
        recording_path: str,
        subject_id: str,
        channel_count: int,
        sample_rate_hz: float,
        duration_sec: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._recording_path = recording_path
        self._subject_id = subject_id
        self._channel_count = channel_count
        self._sample_rate_hz = float(sample_rate_hz)
        self._duration_sec = float(duration_sec)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RawEEG:
        return RawEEG(
            subject_id=self._subject_id,
            channel_count=self._channel_count,
            sample_rate_hz=self._sample_rate_hz,
            duration_sec=self._duration_sec,
            fetched_at=datetime.now(timezone.utc),
        )
