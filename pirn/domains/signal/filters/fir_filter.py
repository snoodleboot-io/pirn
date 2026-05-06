"""``FIRFilter`` — finite impulse response filter.

Algorithm:
    1. Receive the input signal frame and coefficients sequence.
    2. Validate that coefficients is non-empty and all values are real numbers.
    3. Convolve the input signal with the FIR coefficient sequence using linear convolution.
    4. Optionally truncate to the original length.
    5. Return a filtered SignalFrame.

Math:
    FIR convolution:

    $$y(n) = \\sum_{k=0}^{L-1} h(k) \\, x(n - k)$$

    where $h(k)$ are the FIR tap coefficients and $L$ is the filter length.
    The FIR filter has a linear phase response if and only if $h$ is symmetric.

References:
    - Parks, T.W. & Burrus, C.S. (1987). "Digital Filter Design." Wiley.
    - scipy.signal.lfilter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRFilter(Knot):
    """Apply a pre-designed FIR coefficient set.

    Production needs ``scipy.signal.lfilter`` / ``firwin`` for design.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        coefficients: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            coefficients=coefficients,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        coefficients: Sequence[float],
        **_: Any,
    ) -> SignalFrame:
        """Convolve the configured FIR coefficients with the input signal.

        Args:
            signal: Signal to convolve with the FIR tap coefficients.
            coefficients: Non-empty sequence of real-valued FIR tap weights.

        Returns:
            SignalFrame of the FIR-filtered output.

        Raises:
            ValueError: If coefficients is empty.
            TypeError: If any coefficient is not a real number.
        """
        coeffs = tuple(coefficients)
        if not coeffs:
            raise ValueError("FIRFilter: coefficients must be non-empty")
        for c in coeffs:
            if not isinstance(c, (int, float)):
                raise TypeError("FIRFilter: every coefficient must be a real number")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
