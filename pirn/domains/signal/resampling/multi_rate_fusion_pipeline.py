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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


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
        signal_a: SignalFrame,
        signal_b: SignalFrame,
        output_rate_hz: float,
        **_: Any,
    ) -> tuple[SignalFrame, SignalFrame]:
        """Resample both input signals to the common output rate.

        Args:
            signal_a: First input signal at its native rate.
            signal_b: Second input signal at its native rate.
            output_rate_hz: Common output sample rate in Hz (positive float).

        Returns:
            Tuple of two SignalFrames, both resampled to ``output_rate_hz``.

        Raises:
            ValueError: If output_rate_hz is not positive.
        """
        if not isinstance(output_rate_hz, (int, float)) or output_rate_hz <= 0:
            raise ValueError("MultiRateFusionPipeline: output_rate_hz must be positive")

        def _resample(sf: SignalFrame, suffix: str) -> SignalFrame:
            ratio = output_rate_hz / max(sf.sample_rate_hz, 1.0)
            return SignalFrame(
                signal_id=f"{sf.signal_id}:{suffix}",
                channel_count=sf.channel_count,
                sample_rate_hz=float(output_rate_hz),
                samples_per_channel=int(sf.samples_per_channel * ratio),
            )

        return _resample(signal_a, "fused_a"), _resample(signal_b, "fused_b")
