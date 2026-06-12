"""``Decimator`` — anti-alias filter then integer downsample.

Algorithm:
    1. Receive the input signal frame and decimation_factor.
    2. Validate decimation_factor (integer > 1).
    3. Apply a lowpass anti-aliasing filter with cutoff at fs / (2 * decimation_factor).
    4. Keep every Mth sample from the filtered signal.
    5. Return a SignalFrame at the reduced sample rate with the proportionally smaller sample count.

Math:
    Decimated sample rate:

    $$f_{s,\\text{out}} = \\frac{f_s}{M}$$

    Decimated sample count:

    $$N_{\\text{out}} = \\left\\lfloor \\frac{N_{\\text{in}}}{M} \\right\\rfloor$$

    Anti-alias cutoff:

    $$f_c = \\frac{f_s}{2M}$$

References:
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing." Prentice-Hall.
    - scipy.signal.decimate: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.decimate.html
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


def _decimate(data: np.ndarray, decimation_factor: int) -> np.ndarray:
    return ss.decimate(data, q=decimation_factor, axis=-1)


class Decimator(Knot):
    """Decimate by an integer factor using scipy anti-alias filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        decimation_factor: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            decimation_factor=decimation_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        decimation_factor: int,
        **_: Any,
    ) -> SignalPayload:
        """Anti-alias filter and decimate the signal by the configured integer factor.

        Args:
            signal: Signal to anti-alias filter and downsample.
            decimation_factor: Integer downsampling factor (must be > 1).

        Returns:
            SignalPayload at the reduced sample rate with a proportionally smaller sample count.

        Raises:
            ValueError: If decimation_factor is not an integer > 1.
        """
        if not isinstance(decimation_factor, int) or decimation_factor <= 1:
            raise ValueError("Decimator: decimation_factor must be an integer > 1")

        decimated = await asyncio.to_thread(_decimate, signal.data, decimation_factor)

        new_frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:decimate",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz / decimation_factor,
            samples_per_channel=signal.frame.samples_per_channel // decimation_factor,
        )
        return SignalPayload(metadata=new_frame, data=decimated)
