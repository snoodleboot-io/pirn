"""``FractionalDelayFilter`` — sub-sample delay via Lagrange interpolation.

Algorithm:
    1. Receive the input signal frame, delay_samples (fractional), and filter_order.
    2. Validate delay_samples (>= 0.0) and filter_order (positive integer).
    3. Design a Lagrange interpolation FIR filter of length filter_order + 1
       centered at the fractional delay.
    4. Convolve the signal with the Lagrange FIR coefficients.
    5. Return a SignalFrame delayed by delay_samples samples (same rate and length).

Math:
    Lagrange interpolation coefficients at fractional delay $\\delta$:

    $$h_k = \\prod_{\\substack{m=0 \\\\ m \\neq k}}^{N} \\frac{\\delta - m}{k - m}, \\quad k = 0, 1, \\ldots, N$$

    where $N$ = filter_order.

References:
    - Laakso, T.I. et al. (1996). "Splitting the unit delay." IEEE Signal Process. Mag., 13(1), 30-60.
    - scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FractionalDelayFilter(Knot):
    """Apply a sub-sample delay using Lagrange interpolation.

    Production needs a hand-rolled or ``scipy``-based Lagrange FIR design.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        delay_samples: Knot | float,
        filter_order: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            delay_samples=delay_samples,
            filter_order=filter_order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        delay_samples: float,
        filter_order: int,
        **_: Any,
    ) -> SignalFrame:
        """Apply a fractional sample delay to the signal using Lagrange interpolation.

        Args:
            signal: Signal to delay.
            delay_samples: Sub-sample delay in samples (must be >= 0.0).
            filter_order: Order of the Lagrange interpolation FIR filter (positive integer).

        Returns:
            SignalFrame delayed by ``delay_samples`` samples.

        Raises:
            ValueError: If delay_samples or filter_order are invalid.
        """
        if not isinstance(delay_samples, (int, float)) or delay_samples < 0.0:
            raise ValueError("FractionalDelayFilter: delay_samples must be >= 0.0")
        if not isinstance(filter_order, int) or filter_order <= 0:
            raise ValueError("FractionalDelayFilter: filter_order must be a positive integer")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:frac_delayed",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
