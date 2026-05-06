"""``RationalResamplerPipeline`` — upsample / filter / downsample at a ratio.

Algorithm:
    1. Receive the input signal frame, upsample_factor (L), and downsample_factor (M).
    2. Validate both factors (positive integers).
    3. Reduce L and M by their GCD to find the minimal rational ratio.
    4. Upsample by L (zero-stuffing), apply an anti-alias FIR lowpass filter,
       then downsample by M.
    5. Return a SignalFrame at the converted rate with the scaled sample count.

Math:
    GCD-reduced rational ratio:

    $$\\frac{L'}{M'} = \\frac{L / \\gcd(L, M)}{M / \\gcd(L, M)}$$

    Converted sample rate:

    $$f_{s,\\text{out}} = f_{s,\\text{in}} \\cdot \\frac{L'}{M'}$$

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing." Prentice-Hall.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

from math import gcd
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class RationalResamplerPipeline(Knot):
    """Rational sample-rate conversion at ratio L/M.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: Knot | int,
        downsample_factor: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            upsample_factor=upsample_factor,
            downsample_factor=downsample_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        upsample_factor: int,
        downsample_factor: int,
        **_: Any,
    ) -> SignalFrame:
        """Resample the signal at the reduced rational L/M ratio.

        Args:
            signal: Signal to convert to the rational sample rate.
            upsample_factor: Integer upsampling factor L (positive integer).
            downsample_factor: Integer downsampling factor M (positive integer).

        Returns:
            SignalFrame at the new sample rate with GCD-reduced upsample and downsample factors applied.

        Raises:
            ValueError: If upsample_factor or downsample_factor are not positive integers.
        """
        if not isinstance(upsample_factor, int) or upsample_factor <= 0:
            raise ValueError(
                "RationalResamplerPipeline: upsample_factor must be a positive integer"
            )
        if not isinstance(downsample_factor, int) or downsample_factor <= 0:
            raise ValueError(
                "RationalResamplerPipeline: downsample_factor must be a positive integer"
            )
        common = gcd(upsample_factor, downsample_factor)
        up = upsample_factor // common
        m = downsample_factor // common
        new_rate = (signal.sample_rate_hz * up) / m
        new_samples = (signal.samples_per_channel * up) // m
        return SignalFrame(
            signal_id=f"{signal.signal_id}:rational",
            channel_count=signal.channel_count,
            sample_rate_hz=new_rate,
            samples_per_channel=new_samples,
        )
