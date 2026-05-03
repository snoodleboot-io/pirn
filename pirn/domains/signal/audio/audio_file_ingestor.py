"""``AudioFileIngestor`` — load an audio file into a :class:`SignalFrame` reference."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioFileIngestor(Knot):
    """Emit a :class:`SignalFrame` reference for an audio file.

    Production needs ``librosa.load`` (or ``soundfile.read``) to read
    samples from disk; this stub validates the path and emits a typed
    reference suitable for downstream wiring.
    """

    def __init__(
        self,
        *,
        path: str,
        sample_rate_hz: float,
        channel_count: int,
        samples_per_channel: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError(
                "AudioFileIngestor: path must be a non-empty string"
            )
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError(
                "AudioFileIngestor: sample_rate_hz must be positive"
            )
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise ValueError(
                "AudioFileIngestor: channel_count must be a positive integer"
            )
        if (
            not isinstance(samples_per_channel, int)
            or samples_per_channel < 0
        ):
            raise ValueError(
                "AudioFileIngestor: samples_per_channel must be non-negative"
            )
        self._path = path
        self._sample_rate_hz = float(sample_rate_hz)
        self._channel_count = channel_count
        self._samples_per_channel = samples_per_channel
        super().__init__(_config=_config, **kwargs)

    @property
    def path(self) -> str:
        return self._path

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def channel_count(self) -> int:
        return self._channel_count

    @property
    def samples_per_channel(self) -> int:
        return self._samples_per_channel

    async def process(self, **_: Any) -> SignalFrame:
        """Resolve the configured audio file path and return a typed SignalFrame reference.

        Returns:
            SignalFrame reference built from the configured path, sample rate, channel count, and sample count.
        """
        return SignalFrame(
            signal_id=self._path,
            channel_count=self._channel_count,
            sample_rate_hz=self._sample_rate_hz,
            samples_per_channel=self._samples_per_channel,
            fetched_at=datetime.now(timezone.utc),
        )
