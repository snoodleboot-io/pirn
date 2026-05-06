"""``MEGRawIngestor`` — load a raw MEG recording from disk.

Production version uses ``mne.io.read_raw_fif`` /
``mne.io.read_raw_ctf``. This stub validates the path and returns a
:class:`SignalFrame` summary derived from configuration.

Algorithm:
    1. Receive recording_path, signal_id, channel_count, sample_rate_hz, and samples_per_channel.
    2. Validate types and that numeric values are positive and strings are non-empty.
    3. Open the MEG file and read the header metadata.
    4. Construct and return a SignalFrame from the metadata.


References:
    - MNE read_raw_fif: https://mne.tools/stable/generated/mne.io.read_raw_fif.html
    - CTF MEG: https://www.ctf.com/
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class MEGRawIngestor(Knot):
    """Load a raw MEG recording into a :class:`SignalFrame` summary."""

    def __init__(
        self,
        *,
        recording_path: Knot | str,
        signal_id: Knot | str,
        channel_count: Knot | int,
        sample_rate_hz: Knot | float,
        samples_per_channel: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            recording_path=recording_path,
            signal_id=signal_id,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            samples_per_channel=samples_per_channel,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        recording_path: str,
        signal_id: str,
        channel_count: int,
        sample_rate_hz: float,
        samples_per_channel: int,
        **_: Any,
    ) -> SignalFrame:
        """Load the MEG recording from disk and return a SignalFrame summary.

        Args:
            recording_path: Non-empty path string to the MEG file.
            signal_id: Non-empty string identifying the signal.
            channel_count: Positive integer number of MEG channels.
            sample_rate_hz: Positive sample rate in Hz.
            samples_per_channel: Positive number of samples per channel.

        Returns:
            A SignalFrame containing channel count, sample rate, samples per channel, and ingest timestamp.

        Raises:
            ValueError: If any string is empty or any numeric value is non-positive.
        """
        for label, value in (
            ("recording_path", recording_path),
            ("signal_id", signal_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"MEGRawIngestor: {label} must be a non-empty string")
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise ValueError("MEGRawIngestor: channel_count must be a positive int")
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError("MEGRawIngestor: sample_rate_hz must be a positive number")
        if not isinstance(samples_per_channel, int) or samples_per_channel <= 0:
            raise ValueError("MEGRawIngestor: samples_per_channel must be a positive int")
        return SignalFrame(
            signal_id=signal_id,
            channel_count=channel_count,
            sample_rate_hz=float(sample_rate_hz),
            samples_per_channel=samples_per_channel,
            fetched_at=datetime.now(UTC),
        )
