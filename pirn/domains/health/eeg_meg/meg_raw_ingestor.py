"""``MEGRawIngestor`` — load a raw MEG recording from disk.

Production version uses ``mne.io.read_raw_fif`` /
``mne.io.read_raw_ctf``. This stub validates the path and returns a
:class:`SignalFrame` summary derived from configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class MEGRawIngestor(Knot):
    """Load a raw MEG recording into a :class:`SignalFrame` summary."""

    def __init__(
        self,
        *,
        recording_path: str,
        signal_id: str,
        channel_count: int,
        sample_rate_hz: float,
        samples_per_channel: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("recording_path", recording_path),
            ("signal_id", signal_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"MEGRawIngestor: {label} must be a non-empty string"
                )
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise ValueError(
                "MEGRawIngestor: channel_count must be a positive int"
            )
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError(
                "MEGRawIngestor: sample_rate_hz must be a positive number"
            )
        if not isinstance(samples_per_channel, int) or samples_per_channel <= 0:
            raise ValueError(
                "MEGRawIngestor: samples_per_channel must be a positive int"
            )
        self._recording_path = recording_path
        self._signal_id = signal_id
        self._channel_count = channel_count
        self._sample_rate_hz = float(sample_rate_hz)
        self._samples_per_channel = samples_per_channel
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SignalFrame:
        """Load the MEG recording from disk and return a SignalFrame summary.

        Returns:
            A SignalFrame containing channel count, sample rate, samples per channel, and ingest timestamp.
        """
        return SignalFrame(
            signal_id=self._signal_id,
            channel_count=self._channel_count,
            sample_rate_hz=self._sample_rate_hz,
            samples_per_channel=self._samples_per_channel,
            fetched_at=datetime.now(timezone.utc),
        )
