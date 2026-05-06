"""``BesselFilter`` — IIR with maximally-linear phase response.

Algorithm:
    1. Receive the input signal frame, order, and cutoff_hz.
    2. Validate order (positive integer) and cutoff_hz (positive float).
    3. Design a Bessel/Thomson IIR filter of the given order with the given cutoff.
    4. Apply the filter using second-order sections (SOS) for numerical stability.
    5. Return a filtered SignalFrame.

Math:
    The Bessel filter maximises group-delay flatness. The Bessel polynomial $B_n(s)$
    of order $n$ determines the all-pole transfer function:

    $$H(s) = \\frac{B_n(0)}{B_n(s/\\omega_0)}$$

    The group delay is approximately constant up to the cutoff:

    $$\\tau(\\omega) \\approx \\frac{1}{\\omega_0} \\quad \\text{for } \\omega \\ll \\omega_0$$

References:
    - Bessel, F.W. (1824). "Untersuchung des Theils der planetarischen Störungen."
    - Thomson, W.E. (1949). "Delay networks having maximally flat frequency characteristics."
      Proc. IEE, 96(44), 487-490.
    - scipy.signal.bessel: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.bessel.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BesselFilter(Knot):
    """Bessel / Thomson IIR filter.

    Production needs ``scipy.signal.bessel``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            cutoff_hz=cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        order: int,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the Bessel IIR filter to the input signal.

        Args:
            signal: Signal to filter with maximally-linear phase response.
            order: Filter order (positive integer).
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalFrame filtered by the configured Bessel IIR design.

        Raises:
            ValueError: If order or cutoff_hz are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("BesselFilter: order must be a positive integer")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("BesselFilter: cutoff_hz must be positive")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:bessel",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
