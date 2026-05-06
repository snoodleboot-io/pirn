"""``AudioFileIngestor`` — load an audio file into a :class:`SignalFrame` reference.

Algorithm:
    1. Receive path, sample_rate_hz, channel_count, and samples_per_channel.
    2. Validate all parameters.
    3. Construct and return a SignalFrame with the given metadata, recording the
       current UTC timestamp as fetched_at.


References:
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
    - soundfile library: https://python-soundfile.readthedocs.io/
"""

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
        path: Knot | str,
        sample_rate_hz: Knot | float,
        channel_count: Knot | int,
        samples_per_channel: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            path=path,
            sample_rate_hz=sample_rate_hz,
            channel_count=channel_count,
            samples_per_channel=samples_per_channel,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        path: str,
        sample_rate_hz: float,
        channel_count: int,
        samples_per_channel: int,
        **_: Any,
    ) -> SignalFrame:
        """Resolve the configured audio file path and return a typed SignalFrame reference.

        Args:
            path: Non-empty path string to the audio file.
            sample_rate_hz: Positive sample rate in Hz.
            channel_count: Positive integer number of channels.
            samples_per_channel: Non-negative integer number of samples per channel.

        Returns:
            SignalFrame reference built from the configured parameters.

        Raises:
            ValueError: If any parameter is invalid.
        """
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
        return SignalFrame(
            signal_id=path,
            channel_count=channel_count,
            sample_rate_hz=float(sample_rate_hz),
            samples_per_channel=samples_per_channel,
            fetched_at=datetime.now(timezone.utc),
        )
