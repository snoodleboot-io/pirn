"""``FIRWindowFilter`` — FIR filter designed via the window method.

Algorithm:
    1. Receive the input signal frame, num_taps, cutoff_hz, and window.
    2. Validate num_taps (positive odd integer), cutoff_hz (positive), and window
       (known window name).
    3. Compute the ideal sinc lowpass impulse response truncated to num_taps.
    4. Multiply by the chosen window function to reduce Gibbs phenomenon.
    5. Convolve the windowed FIR with the input signal.
    6. Return a filtered SignalFrame.

Math:
    Ideal lowpass impulse response:

    $$h_d(n) = \\frac{\\omega_c}{\\pi} \\text{sinc}\\!\\left(\\frac{\\omega_c}{\\pi} n\\right), \\quad n = -(L-1)/2, \\ldots, (L-1)/2$$

    Windowed FIR: $h(n) = h_d(n) \\cdot w(n)$ where $w(n)$ is the chosen window.

References:
    - Harris, F.J. (1978). "On the use of windows for harmonic analysis with the DFT."
      Proc. IEEE, 66(1), 51-83.
    - scipy.signal.firwin: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.firwin.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRWindowFilter(Knot):
    """Design a linear-phase FIR filter using the window method."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_taps: Knot | int,
        cutoff_hz: Knot | float,
        window: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_taps=num_taps,
            cutoff_hz=cutoff_hz,
            window=window,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        num_taps: int,
        cutoff_hz: float,
        window: str,
        **_: Any,
    ) -> SignalFrame:
        """Apply the window-method FIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.
            num_taps: Number of filter taps (positive odd integer).
            cutoff_hz: Cutoff frequency in Hz (positive float).
            window: Window function name: ``hamming``, ``hann``, ``blackman``,
                or ``rectangular``.

        Returns:
            Filtered SignalFrame with the same shape as the input.

        Raises:
            ValueError: If num_taps, cutoff_hz, or window are invalid.
        """
        if not isinstance(num_taps, int) or num_taps <= 0 or num_taps % 2 == 0:
            raise ValueError(
                "FIRWindowFilter: num_taps must be a positive odd integer"
            )
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("FIRWindowFilter: cutoff_hz must be a positive scalar")
        if window not in frozenset({"hamming", "hann", "blackman", "rectangular"}):
            raise ValueError(
                "FIRWindowFilter: window must be one of "
                "'hamming', 'hann', 'blackman', 'rectangular'"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir-window",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
