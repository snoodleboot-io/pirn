"""``ArbitraryResamplerPipeline`` — resample to any target rate via polyphase rational resampling.

Algorithm:
    1. Receive the input signal frame, input_rate_hz, and output_rate_hz.
    2. Validate both rates (positive floats).
    3. Compute the exact upsample (L) and downsample (M) factors in lowest terms from
       the rates' decimal values (``22050 / 1000 = 441 / 20``), never from their
       integer parts.
    4. Apply ``scipy.signal.resample_poly`` with L/M when both are at most 10000;
       otherwise resample at the exact ratio by bandlimited interpolation
       (``PolyResampling.resample_rate``).
    5. Return a SignalPayload at the target rate with proportionally scaled sample count.

Math:
    Sample count conversion:

    $$N_{\\text{out}} = \\left\\lceil N_{\\text{in}} \\cdot \\frac{f_{\\text{out}}}{f_{\\text{in}}} \\right\\rceil$$

    Polyphase ratio:

    $$\\frac{L}{M} = \\frac{f_{\\text{out}}}{f_{\\text{in}}}, \\qquad \\gcd(L, M) = 1$$

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing." Prentice-Hall.
    - scipy.signal.resample_poly: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.resampling._poly_resampling import PolyResampling
from pirn_signal.types.signal_payload import SignalPayload


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

        result = await asyncio.to_thread(
            PolyResampling.resample_rate, signal.data, float(input_rate_hz), float(output_rate_hz)
        )

        return signal.derive(
            "resampled",
            result,
            sample_rate_hz=float(output_rate_hz),
        )
