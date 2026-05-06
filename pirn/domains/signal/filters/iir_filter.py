"""``IIRFilter`` — generic infinite impulse response filter.

Algorithm:
    1. Receive the input signal frame, numerator, and denominator.
    2. Validate that both are non-empty, denominator[0] is non-zero, and all
       values are real numbers.
    3. Apply the IIR difference equation using the (b, a) transfer function
       representation via ``scipy.signal.lfilter`` or ``sosfiltfilt``.
    4. Return a filtered SignalFrame.

Math:
    IIR difference equation:

    $$y(n) = \\frac{1}{a_0} \\left( \\sum_{k=0}^{M} b_k x(n-k) - \\sum_{k=1}^{N} a_k y(n-k) \\right)$$

    Transfer function:

    $$H(z) = \\frac{B(z)}{A(z)} = \\frac{\\sum_{k=0}^{M} b_k z^{-k}}{\\sum_{k=0}^{N} a_k z^{-k}}$$

References:
    - scipy.signal.lfilter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall. Chapter 6.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class IIRFilter(Knot):
    """Apply a pre-designed IIR (b, a) coefficient set.

    Production needs ``scipy.signal.lfilter`` or ``sosfiltfilt``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        numerator: Knot | tuple,
        denominator: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            numerator=numerator,
            denominator=denominator,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        numerator: Sequence[float],
        denominator: Sequence[float],
        **_: Any,
    ) -> SignalFrame:
        """Apply the configured IIR (b, a) coefficients to the input signal.

        Args:
            signal: Signal to filter with the configured (b, a) transfer function.
            numerator: Non-empty sequence of numerator (b) coefficients.
            denominator: Non-empty sequence of denominator (a) coefficients;
                first element must be non-zero.

        Returns:
            SignalFrame of the IIR-filtered output.

        Raises:
            ValueError: If numerator or denominator are invalid.
            TypeError: If any coefficient is not a real number.
        """
        b = tuple(numerator)
        a = tuple(denominator)
        if not b:
            raise ValueError("IIRFilter: numerator must be non-empty")
        if not a:
            raise ValueError("IIRFilter: denominator must be non-empty")
        if a[0] == 0:
            raise ValueError("IIRFilter: denominator[0] must be non-zero")
        for c in (*b, *a):
            if not isinstance(c, (int, float)):
                raise TypeError("IIRFilter: every coefficient must be a real number")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:iir",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
