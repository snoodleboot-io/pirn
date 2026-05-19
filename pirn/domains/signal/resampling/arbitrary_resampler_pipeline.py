"""``ArbitraryResamplerPipeline`` — resample to any target rate via polyphase rational resampling.

Algorithm:
    1. Receive the input signal frame, input_rate_hz, and output_rate_hz.
    2. Validate both rates (positive floats).
    3. Compute the integer upsample (L) and downsample (M) factors from the
       ratio output_rate_hz / input_rate_hz using a precision multiplier.
    4. Reduce L/M by their GCD to find the minimal polyphase decomposition.
    5. Apply ``scipy.signal.resample_poly`` with the reduced L/M factors.
    6. Return a SignalFrame at the target rate with proportionally scaled sample count.

Math:
    Sample count conversion:

    $$N_{\\text{out}} = \\left\\lfloor N_{\\text{in}} \\cdot \\frac{f_{\\text{out}}}{f_{\\text{in}}} \\right\\rfloor$$

    Polyphase ratio:

    $$\\frac{L}{M} = \\frac{f_{\\text{out}}}{f_{\\text{in}}} \\cdot \\frac{P}{\\gcd(P \\cdot f_{\\text{out}}, P \\cdot f_{\\text{in}})}$$

    where $P$ is the precision multiplier.

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing." Prentice-Hall.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

import asyncio
from math import gcd
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _resample_poly(data: np.ndarray, up: int, down: int) -> np.ndarray:
    return np.asarray(ss.resample_poly(data, up, down, axis=-1))


class ArbitraryResamplerPipeline(Knot):
    """Resample from any input rate to any output rate using polyphase rational resampling.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        input_rate_hz: Knot | float,
        output_rate_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            input_rate_hz=input_rate_hz,
            output_rate_hz=output_rate_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        input_rate_hz: float,
        output_rate_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Resample the signal from the input rate to the output rate.

        Args:
            signal: Signal to resample.
            input_rate_hz: Original sample rate in Hz (positive float).
            output_rate_hz: Target sample rate in Hz (positive float).

        Returns:
            SignalPayload at ``output_rate_hz`` with sample count scaled proportionally.

        Raises:
            ValueError: If input_rate_hz or output_rate_hz are not positive.
        """
        if not isinstance(input_rate_hz, (int, float)) or input_rate_hz <= 0:
            raise ValueError("ArbitraryResamplerPipeline: input_rate_hz must be positive")
        if not isinstance(output_rate_hz, (int, float)) or output_rate_hz <= 0:
            raise ValueError("ArbitraryResamplerPipeline: output_rate_hz must be positive")

        common = gcd(int(input_rate_hz), int(output_rate_hz))
        up = int(output_rate_hz) // common
        down = int(input_rate_hz) // common

        result = await asyncio.to_thread(_resample_poly, signal.data, up, down)

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:resampled",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=float(output_rate_hz),
                samples_per_channel=result.shape[-1],
            ),
            data=result,
        )
