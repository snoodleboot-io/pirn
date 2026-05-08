"""``MultiRateFusionPipeline`` — fuse two signals at different rates by resampling to a common rate.

Algorithm:
    1. Receive two signal frames (signal_a, signal_b) and the output_rate_hz.
    2. Validate output_rate_hz (positive float).
    3. Compute the resampling ratio for each signal relative to output_rate_hz.
    4. Apply polyphase resampling (``scipy.signal.resample_poly``) to each signal.
    5. Return a tuple of two SignalFrames both at output_rate_hz with aligned sample counts.

Math:
    Resampling ratio for signal $i$:

    $$\\alpha_i = \\frac{f_{\\text{out}}}{f_{s,i}}$$

    Aligned sample count:

    $$N_{\\text{out},i} = \\left\\lfloor N_{\\text{in},i} \\cdot \\alpha_i \\right\\rfloor$$

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


def _resample_to_rate(
    data: np.ndarray,
    src_rate: float,
    tgt_rate: float,
) -> np.ndarray:
    common = gcd(int(tgt_rate), int(src_rate))
    up = int(tgt_rate) // common
    down = int(src_rate) // common
    return np.asarray(ss.resample_poly(data, up, down, axis=-1))


class MultiRateFusionPipeline(Knot):
    """Fuse two signals sampled at different rates by resampling both to a common output rate.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal_a: Knot,
        signal_b: Knot,
        output_rate_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal_a=signal_a,
            signal_b=signal_b,
            output_rate_hz=output_rate_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal_a: SignalPayload,
        signal_b: SignalPayload,
        output_rate_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Resample both input signals to the common output rate and average them.

        Args:
            signal_a: First input signal at its native rate.
            signal_b: Second input signal at its native rate.
            output_rate_hz: Common output sample rate in Hz (positive float).

        Returns:
            SignalPayload at ``output_rate_hz`` containing the averaged fused signal.

        Raises:
            ValueError: If output_rate_hz is not positive.
        """
        if not isinstance(output_rate_hz, (int, float)) or output_rate_hz <= 0:
            raise ValueError("MultiRateFusionPipeline: output_rate_hz must be positive")

        ra, rb = await asyncio.gather(
            asyncio.to_thread(
                _resample_to_rate,
                signal_a.data,
                signal_a.frame.sample_rate_hz,
                float(output_rate_hz),
            ),
            asyncio.to_thread(
                _resample_to_rate,
                signal_b.data,
                signal_b.frame.sample_rate_hz,
                float(output_rate_hz),
            ),
        )

        n_out = min(ra.shape[-1], rb.shape[-1])
        fused = (ra[..., :n_out] + rb[..., :n_out]) / 2.0

        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal_a.frame.signal_id}:fused",
                channel_count=signal_a.frame.channel_count,
                sample_rate_hz=float(output_rate_hz),
                samples_per_channel=n_out,
            ),
            data=fused,
        )
