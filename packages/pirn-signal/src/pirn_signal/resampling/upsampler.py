"""``Upsampler`` — zero-stuff upsample (no filter).

Algorithm:
    1. Receive the input signal frame and upsample_factor.
    2. Validate upsample_factor (integer > 1).
    3. Insert (upsample_factor - 1) zeros between each input sample.
    4. Return a SignalFrame at the higher sample rate with the proportionally
       larger sample count (no reconstruction filter applied).

Math:
    Upsampled sample rate:

    $$f_{s,\\text{out}} = L \\cdot f_{s,\\text{in}}$$

    Upsampled sample count:

    $$N_{\\text{out}} = L \\cdot N_{\\text{in}}$$

    where $L$ = upsample_factor.

References:
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing." Prentice-Hall.
    - numpy: https://numpy.org/doc/stable/
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


def _zero_stuff(data: np.ndarray, factor: int) -> np.ndarray:
    shape = list(data.shape)
    shape[-1] = shape[-1] * factor
    out = np.zeros(shape, dtype=data.dtype)
    out[..., ::factor] = data
    return out


class Upsampler(Knot):
    """Insert zeros between samples by an integer factor."""

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            upsample_factor=upsample_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        upsample_factor: int,
        **_: Any,
    ) -> SignalPayload:
        """Zero-stuff the signal by the configured integer factor and return the upsampled SignalPayload.

        Args:
            signal: Signal to upsample by inserting zeros between each sample.
            upsample_factor: Integer upsampling factor (must be > 1).

        Returns:
            SignalPayload at the higher sample rate with zeros inserted between original samples.

        Raises:
            ValueError: If upsample_factor is not an integer > 1.
        """
        if not isinstance(upsample_factor, int) or upsample_factor <= 1:
            raise ValueError("Upsampler: upsample_factor must be an integer > 1")

        upsampled = await asyncio.to_thread(_zero_stuff, signal.data, upsample_factor)

        new_frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:upsample",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz * upsample_factor,
            samples_per_channel=signal.frame.samples_per_channel * upsample_factor,
        )
        return SignalPayload(metadata=new_frame, data=upsampled)
