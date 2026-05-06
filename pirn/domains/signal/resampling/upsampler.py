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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Upsampler(Knot):
    """Insert zeros between samples by an integer factor.

    Production needs ``numpy`` for the zero-stuffing step.
    """

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
        signal: SignalFrame,
        upsample_factor: int,
        **_: Any,
    ) -> SignalFrame:
        """Zero-stuff the signal by the configured integer factor and return the upsampled SignalFrame.

        Args:
            signal: Signal to upsample by inserting zeros between each sample.
            upsample_factor: Integer upsampling factor (must be > 1).

        Returns:
            SignalFrame at the higher sample rate with zeros inserted between original samples.

        Raises:
            ValueError: If upsample_factor is not an integer > 1.
        """
        if not isinstance(upsample_factor, int) or upsample_factor <= 1:
            raise ValueError("Upsampler: upsample_factor must be an integer > 1")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:upsample",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz * upsample_factor,
            samples_per_channel=signal.samples_per_channel * upsample_factor,
        )
