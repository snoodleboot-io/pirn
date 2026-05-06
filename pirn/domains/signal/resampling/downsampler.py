"""``Downsampler`` — drop samples (no filter).

Algorithm:
    1. Receive the input signal frame and downsample_factor.
    2. Validate downsample_factor (integer > 1).
    3. Keep every Nth sample from the input signal without applying any
       anti-aliasing filter (caller is responsible for prior filtering).
    4. Return a SignalFrame at the reduced sample rate with the proportionally
       smaller sample count.

Math:
    Downsampled sample rate:

    $$f_{s,\\text{out}} = \\frac{f_s}{N}$$

    Downsampled sample count:

    $$N_{\\text{out}} = \\left\\lfloor \\frac{N_{\\text{in}}}{N} \\right\\rfloor$$

References:
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing." Prentice-Hall.
    - numpy indexing: https://numpy.org/doc/stable/user/basics.indexing.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Downsampler(Knot):
    """Keep every Nth sample (caller is responsible for anti-aliasing).

    Production needs ``numpy`` indexing only.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        downsample_factor: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            downsample_factor=downsample_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        downsample_factor: int,
        **_: Any,
    ) -> SignalFrame:
        """Keep every Nth sample from the signal and return the down-sampled SignalFrame.

        Args:
            signal: Signal to downsample by the configured factor (no anti-alias filter applied).
            downsample_factor: Integer downsampling factor (must be > 1).

        Returns:
            SignalFrame at the reduced sample rate with every Nth sample retained.

        Raises:
            ValueError: If downsample_factor is not an integer > 1.
        """
        if not isinstance(downsample_factor, int) or downsample_factor <= 1:
            raise ValueError(
                "Downsampler: downsample_factor must be an integer > 1"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:downsample",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz / downsample_factor,
            samples_per_channel=signal.samples_per_channel // downsample_factor,
        )
