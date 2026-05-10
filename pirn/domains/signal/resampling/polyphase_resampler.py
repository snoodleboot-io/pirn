"""``PolyphaseResampler`` — polyphase rate-conversion filter bank.

Algorithm:
    1. Receive the input signal frame, upsample_factor (L), downsample_factor (M),
       and filter_length.
    2. Validate all three parameters (positive integers).
    3. Design an anti-alias FIR prototype of length filter_length with cutoff
       at 1 / (2 * max(L, M)).
    4. Decompose the FIR prototype into L polyphase branches.
    5. Apply ``scipy.signal.upfirdn`` with (L, M) to produce the resampled output.
    6. Return a SignalFrame at the new rate fs * L / M with scaled sample count.

Math:
    Polyphase resampled rate:

    $$f_{s,\\text{out}} = f_{s,\\text{in}} \\cdot \\frac{L}{M}$$

    Resampled sample count:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\frac{L}{M} \\right\\rfloor$$

References:
    - Harris, F.J. (2004). "Multirate Signal Processing for Communication Systems." Prentice-Hall.
    - scipy.signal.upfirdn: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.upfirdn.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _resample_poly(data: np.ndarray, up: int, down: int) -> np.ndarray:
    return np.asarray(ss.resample_poly(data, up, down, axis=-1))


class PolyphaseResampler(Knot):
    """Polyphase resampler at integer L/M ratio with anti-alias FIR.

    Production needs ``scipy.signal.upfirdn`` or ``resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: Knot | int,
        downsample_factor: Knot | int,
        filter_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            upsample_factor=upsample_factor,
            downsample_factor=downsample_factor,
            filter_length=filter_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        upsample_factor: int,
        downsample_factor: int,
        filter_length: int,
        **_: Any,
    ) -> SignalPayload:
        """Resample the signal at the configured L/M integer ratio.

        Args:
            signal: Signal to resample using the polyphase filter bank.
            upsample_factor: Integer upsampling factor L (positive integer).
            downsample_factor: Integer downsampling factor M (positive integer).
            filter_length: Number of FIR anti-alias taps (positive integer).

        Returns:
            SignalPayload at the new sample rate computed as ``fs * upsample_factor / downsample_factor``.

        Raises:
            ValueError: If upsample_factor, downsample_factor, or filter_length are invalid.
        """
        if not isinstance(upsample_factor, int) or upsample_factor <= 0:
            raise ValueError("PolyphaseResampler: upsample_factor must be a positive integer")
        if not isinstance(downsample_factor, int) or downsample_factor <= 0:
            raise ValueError("PolyphaseResampler: downsample_factor must be a positive integer")
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError("PolyphaseResampler: filter_length must be a positive integer")

        result = await asyncio.to_thread(
            _resample_poly, signal.data, upsample_factor, downsample_factor
        )
        new_rate = (signal.frame.sample_rate_hz * upsample_factor) / downsample_factor

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:polyphase",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=new_rate,
                samples_per_channel=result.shape[-1],
            ),
            data=result,
        )
