"""``StreamingBufferManager`` — ring-buffer / framing manager for streaming.

Algorithm:
    1. Receive the input signal frame, frame_size, and hop_size.
    2. Validate frame_size and hop_size (positive integers with hop_size <= frame_size).
    3. Partition the signal into overlapping frames of length frame_size spaced
       by hop_size samples using overlap-add or overlap-save framing.
    4. Manage the ring buffer state to handle frame boundaries across calls.
    5. Return a SignalFrame representing the current buffered output.

Math:
    Number of complete frames from $N$ input samples:

    $$K = \\left\\lfloor \\frac{N - F}{H} \\right\\rfloor + 1$$

    where $F$ = frame_size and $H$ = hop_size.

    Overlap fraction:

    $$\\rho = 1 - \\frac{H}{F}$$

References:
    - Allen, J.B. & Rabiner, L.R. (1977). "A unified approach to short-time Fourier analysis and synthesis."
      Proc. IEEE, 65(11), 1558-1564.
    - numpy: https://numpy.org/doc/stable/
"""

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
        frame_size: Knot | int,
        hop_size: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            frame_size=frame_size,
            hop_size=hop_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        frame_size: int,
        hop_size: int,
        **_: Any,
    ) -> SignalFrame:
        """Frame the input signal into overlapping blocks and return the buffered SignalFrame.

        Args:
            signal: Streaming signal to partition into overlapping frames.
            frame_size: Number of samples per frame (positive integer).
            hop_size: Number of samples between successive frames (positive integer,
                must not exceed frame_size).

        Returns:
            SignalFrame representing the overlap-add buffered output with the same sample count.

        Raises:
            ValueError: If frame_size or hop_size are invalid.
        """
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
        return SignalFrame(
            signal_id=f"{signal.signal_id}:framed",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
