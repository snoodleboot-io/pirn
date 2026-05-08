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

import asyncio
from typing import Any

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _load_audio(path: str) -> SignalPayload:
    y, sr = librosa.load(path, sr=None, mono=False)
    if y.ndim == 1:
        y = y[np.newaxis, :]
    return SignalPayload(
        frame=SignalFrame(
            signal_id=path,
            channel_count=y.shape[0],
            sample_rate_hz=float(sr),
            samples_per_channel=y.shape[1],
        ),
        data=y,
    )


class AudioFileIngestor(Knot):
    """Load an audio file from disk into a :class:`SignalPayload`.

    Uses ``librosa.load`` to read samples at the native sample rate,
    preserving all channels.
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
    ) -> SignalPayload:
        """Load the audio file at ``path`` and return a SignalPayload.

        Args:
            path: Non-empty path string to the audio file.
            sample_rate_hz: Positive sample rate in Hz (used for validation only;
                actual rate is read from the file).
            channel_count: Positive integer number of channels (used for validation only).
            samples_per_channel: Non-negative integer (used for validation only).

        Returns:
            SignalPayload with sample data loaded from disk.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if not isinstance(path, str) or not path:
            raise ValueError("AudioFileIngestor: path must be a non-empty string")
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError("AudioFileIngestor: sample_rate_hz must be positive")
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise ValueError("AudioFileIngestor: channel_count must be a positive integer")
        if not isinstance(samples_per_channel, int) or samples_per_channel < 0:
            raise ValueError("AudioFileIngestor: samples_per_channel must be non-negative")
        return await asyncio.to_thread(_load_audio, path)
