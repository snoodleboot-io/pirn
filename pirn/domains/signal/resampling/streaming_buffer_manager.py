"""``StreamingBufferManager`` — ring-buffer / framing manager for streaming."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class StreamingBufferManager(Knot):
    """Manage frame-based streaming buffers (overlap-add / overlap-save).

    Production needs ``numpy`` for the ring buffer (or a typed bytearray
    over a backing audio device).
    """

    def __init__(
        self,
        *,
        signal: Knot,
        frame_size: int,
        hop_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(frame_size, int) or frame_size <= 0:
            raise ValueError(
                "StreamingBufferManager: frame_size must be a positive integer"
            )
        if not isinstance(hop_size, int) or hop_size <= 0:
            raise ValueError(
                "StreamingBufferManager: hop_size must be a positive integer"
            )
        if hop_size > frame_size:
            raise ValueError(
                "StreamingBufferManager: hop_size must not exceed frame_size"
            )
        self._frame_size = frame_size
        self._hop_size = hop_size
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def frame_size(self) -> int:
        return self._frame_size

    @property
    def hop_size(self) -> int:
        return self._hop_size

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:framed",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
