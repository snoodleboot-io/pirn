"""``ButterworthFilter`` — maximally-flat IIR filter (no passband ripple).

Production needs ``scipy.signal.butter`` plus ``scipy.signal.sosfiltfilt``
or equivalent. This stub validates the design parameters and threads a
:class:`SignalFrame` reference through with the same shape.

Algorithm:
    1. Receive the input signal frame, order, cutoff_hz, and band_type.
    2. Validate order (positive integer), band_type (known string), and cutoff_hz
       (positive scalar for lowpass/highpass; (low, high) tuple for bandpass/bandstop).
    3. Design a Butterworth IIR filter of the given order using ``scipy.signal.butter``.
    4. Apply zero-phase filtering via ``sosfiltfilt`` for offline use, or
       causal ``sosfilt`` for realtime.
    5. Return a filtered SignalFrame.

Math:
    Butterworth squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + (\\omega / \\omega_c)^{2n}}$$

    where $n$ = order and $\\omega_c = 2\\pi f_{\\text{cutoff}}$.
    The −3 dB point occurs exactly at $\\omega_c$.

References:
    - Butterworth, S. (1930). "On the theory of filter amplifiers." Wireless Engineer, 7, 536-541.
    - scipy.signal.butter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ButterworthFilter(Knot):
    """Configure and apply a Butterworth IIR filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        cutoff_hz: Knot | float | tuple,
        band_type: Knot | str = "lowpass",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            cutoff_hz=cutoff_hz,
            band_type=band_type,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        order: int,
        cutoff_hz: float | tuple[float, float],
        band_type: str = "lowpass",
        **_: Any,
    ) -> SignalFrame:
        """Apply the Butterworth IIR filter to the input signal.

        Args:
            signal: Signal to filter with a maximally-flat Butterworth design.
            order: Filter order (positive integer).
            cutoff_hz: Cutoff frequency in Hz; scalar for lowpass/highpass,
                (low, high) tuple for bandpass/bandstop.
            band_type: One of ``lowpass``, ``highpass``, ``bandpass``, ``bandstop``.

        Returns:
            SignalFrame filtered by the configured Butterworth IIR.

        Raises:
            ValueError: If order, band_type, or cutoff_hz are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError(
                "ButterworthFilter: order must be a positive integer"
            )
        if band_type not in {"lowpass", "highpass", "bandpass", "bandstop"}:
            raise ValueError(
                "ButterworthFilter: band_type must be one of "
                "'lowpass', 'highpass', 'bandpass', 'bandstop'"
            )
        if band_type in {"bandpass", "bandstop"}:
            if (
                not isinstance(cutoff_hz, tuple)
                or len(cutoff_hz) != 2
                or any(not isinstance(c, (int, float)) for c in cutoff_hz)
            ):
                raise ValueError(
                    "ButterworthFilter: bandpass/bandstop requires (low, high) tuple"
                )
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    "ButterworthFilter: cutoff bounds must satisfy 0 < low < high"
                )
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError(
                    "ButterworthFilter: cutoff_hz must be a positive scalar"
                )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:butter-{band_type}",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
