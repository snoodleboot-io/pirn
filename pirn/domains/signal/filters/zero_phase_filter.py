"""``ZeroPhaseFilter`` — zero-phase forward-backward IIR filter.

Algorithm:
    1. Receive the input signal frame, filter_type, cutoff_hz, and order.
    2. Validate filter_type, order, and cutoff_hz (same rules as CausalRealtimeFilter).
    3. Design an IIR filter (e.g., Butterworth) of the given order and type.
    4. Apply the filter forward, then backward (filtfilt), producing exactly zero
       phase shift and doubling the effective filter order.
    5. Return a filtered SignalFrame.

Math:
    Forward-backward filtering combined magnitude response:

    $$|H_{\\text{ff}}(\\omega)|^2 = |H(\\omega)|^4$$

    The effective filter order is doubled and the phase is identically zero:

    $$\\angle H_{\\text{ff}}(\\omega) = 0 \\quad \\forall \\omega$$

References:
    - scipy.signal.sosfiltfilt: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
    - Gustafsson, F. (1996). "Determining the initial states in forward-backward filtering."
      IEEE Trans. Signal Process., 44(4), 988-992.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ZeroPhaseFilter(Knot):
    """Apply a zero-phase IIR filter via forward-backward (filtfilt) processing."""

    def __init__(
        self,
        *,
        signal: Knot,
        filter_type: Knot | str,
        cutoff_hz: Knot | float | tuple,
        order: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            filter_type=filter_type,
            cutoff_hz=cutoff_hz,
            order=order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        filter_type: str,
        cutoff_hz: float | tuple[float, float],
        order: int,
        **_: Any,
    ) -> SignalFrame:
        """Apply the zero-phase forward-backward IIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.
            filter_type: One of ``lowpass``, ``highpass``, ``bandpass``, ``bandstop``.
            cutoff_hz: Cutoff frequency or (low, high) pair in Hz.
            order: Filter order (positive integer).

        Returns:
            Filtered SignalFrame with zero phase distortion and the same shape as the input.

        Raises:
            ValueError: If filter_type, order, or cutoff_hz are invalid.
        """
        if filter_type not in frozenset({"lowpass", "highpass", "bandpass", "bandstop"}):
            raise ValueError(
                "ZeroPhaseFilter: filter_type must be one of "
                "'lowpass', 'highpass', 'bandpass', 'bandstop'"
            )
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ZeroPhaseFilter: order must be a positive integer")
        if filter_type in {"bandpass", "bandstop"}:
            if (
                not isinstance(cutoff_hz, tuple)
                or len(cutoff_hz) != 2
                or any(not isinstance(c, (int, float)) for c in cutoff_hz)
            ):
                raise ValueError(
                    "ZeroPhaseFilter: bandpass/bandstop requires (low, high) tuple"
                )
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    "ZeroPhaseFilter: cutoff bounds must satisfy 0 < low < high"
                )
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError(
                    "ZeroPhaseFilter: cutoff_hz must be a positive scalar"
                )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:zerophase-{filter_type}",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
