"""``StreamingBufferManager`` — frame a signal into overlapping analysis blocks.

Algorithm:
    1. Receive the input signal, frame_size, and hop_size.
    2. Validate frame_size and hop_size (positive integers with hop_size <= frame_size).
    3. Frame every channel at once with a strided view over the sample array,
       zero-padding the tail so the final partial frame is kept: framing that
       stopped at the last *complete* frame discarded up to ``frame_size - 1``
       trailing samples per channel, silently, on every call.
    4. Return the frames as a SignalPayload shaped
       ``(channels, n_frames, frame_size)`` whose frame records the number of
       input samples the blocks represent — not ``frame_size``, which is the
       trailing axis of a 3-D array and says nothing about signal length.

There is no ring buffer and no state carried between calls: a knot's
``process`` is a pure function of its inputs (state on ``self`` would be shared
by every concurrent run of the same graph), so each call frames exactly the
samples it was given and pads the tail to a whole frame. A caller streaming
successive blocks through this knot passes the overlap it wants to keep as part
of the next input.

Math:
    Number of frames covering $N$ input samples with tail padding:

    $$K = 1 + \\left\\lceil \\frac{\\max(0,\\, N - F)}{H} \\right\\rceil$$

    where $F$ = frame_size and $H$ = hop_size, and the padded length is
    $(K-1)H + F \\ge N$.

    Overlap fraction:

    $$\\rho = 1 - \\frac{H}{F}$$

References:
    - Allen, J.B. & Rabiner, L.R. (1977). "A unified approach to short-time Fourier analysis and synthesis."
      Proc. IEEE, 65(11), 1558-1564.
    - numpy.lib.stride_tricks.sliding_window_view:
      https://numpy.org/doc/stable/reference/generated/numpy.lib.stride_tricks.sliding_window_view.html
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


class StreamingBufferManager(Knot):
    """Frame a signal into overlapping blocks (overlap-add / overlap-save analysis)."""

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
        signal: SignalPayload,
        frame_size: int,
        hop_size: int,
        **_: Any,
    ) -> SignalPayload:
        """Frame the input signal into overlapping blocks and return the buffered SignalPayload.

        Args:
            signal: Streaming signal to partition into overlapping frames.
            frame_size: Number of samples per frame (positive integer).
            hop_size: Number of samples between successive frames (positive integer,
                must not exceed frame_size).

        Returns:
            SignalPayload shaped ``(channels, n_frames, frame_size)``. Every input
            sample appears in at least one frame; the last frame is zero-padded
            when the signal does not end on a frame boundary. The frame's
            ``samples_per_channel`` is the input sample count the blocks cover.

        Raises:
            ValueError: If frame_size or hop_size are invalid.
        """
        if not isinstance(frame_size, int) or frame_size <= 0:
            raise ValueError("StreamingBufferManager: frame_size must be a positive integer")
        if not isinstance(hop_size, int) or hop_size <= 0:
            raise ValueError("StreamingBufferManager: hop_size must be a positive integer")
        if hop_size > frame_size:
            raise ValueError("StreamingBufferManager: hop_size must not exceed frame_size")

        channels = np.atleast_2d(signal.data)
        framed = await asyncio.to_thread(
            StreamingBufferManager._frame_channels, channels, frame_size, hop_size
        )

        return signal.derive(
            "framed",
            framed,
            channel_count=int(channels.shape[0]),
            samples_per_channel=int(channels.shape[-1]),
        )

    @staticmethod
    def _frame_channels(channels: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
        """Frame every channel of a ``(channels, samples)`` array in one strided view.

        Args:
            channels: Sample array shaped ``(channels, samples)``.
            frame_size: Number of samples per frame.
            hop_size: Number of samples between successive frame starts.

        Returns:
            Array of shape ``(channels, n_frames, frame_size)``; the tail is
            zero-padded so no input sample is dropped.
        """
        sample_count = int(channels.shape[-1])
        if sample_count == 0:
            return np.empty((channels.shape[0], 0, frame_size), dtype=channels.dtype)
        frame_count = 1 + math.ceil(max(0, sample_count - frame_size) / hop_size)
        padded_length = (frame_count - 1) * hop_size + frame_size
        padded = (
            channels
            if padded_length == sample_count
            else np.pad(channels, ((0, 0), (0, padded_length - sample_count)))
        )
        windows = np.lib.stride_tricks.sliding_window_view(padded, frame_size, axis=-1)
        return np.ascontiguousarray(windows[:, ::hop_size])
