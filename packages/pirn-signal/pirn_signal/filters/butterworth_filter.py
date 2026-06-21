"""``ButterworthFilter`` — maximally-flat IIR filter (no passband ripple).

Algorithm:
    1. Receive the input signal payload, order, cutoff_hz, and band_type.
    2. Validate order (positive integer), band_type (known string), and cutoff_hz
       (positive scalar for lowpass/highpass; (low, high) tuple for bandpass/bandstop).
    3. Design a Butterworth IIR filter of the given order using ``scipy.signal.butter``.
    4. Apply causal filtering via ``sosfilt``.
    5. Return a filtered SignalPayload.

Math:
    Butterworth squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + (\\omega / \\omega_c)^{2n}}$$

    where $n$ = order and $\\omega_c = 2\\pi f_{\\text{cutoff}}$.
    The -3 dB point occurs exactly at $\\omega_c$.

References:
    - Butterworth, S. (1930). "On the theory of filter amplifiers." Wireless Engineer, 7, 536-541.
    - scipy.signal.butter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


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
        signal: SignalPayload,
        order: int,
        cutoff_hz: float | tuple[float, float],
        band_type: str = "lowpass",
        **_: Any,
    ) -> SignalPayload:
        """Apply the Butterworth IIR filter to the input signal.

        Args:
            signal: Signal payload to filter with a maximally-flat Butterworth design.
            order: Filter order (positive integer).
            cutoff_hz: Cutoff frequency in Hz; scalar for lowpass/highpass,
                (low, high) tuple for bandpass/bandstop.
            band_type: One of ``lowpass``, ``highpass``, ``bandpass``, ``bandstop``.

        Returns:
            SignalPayload filtered by the configured Butterworth IIR.

        Raises:
            ValueError: If order, band_type, or cutoff_hz are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ButterworthFilter: order must be a positive integer")
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
                raise ValueError("ButterworthFilter: bandpass/bandstop requires (low, high) tuple")
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError("ButterworthFilter: cutoff bounds must satisfy 0 < low < high")
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError("ButterworthFilter: cutoff_hz must be a positive scalar")

        fs = signal.frame.sample_rate_hz
        btype_map = {
            "lowpass": "low",
            "highpass": "high",
            "bandpass": "bandpass",
            "bandstop": "bandstop",
        }
        sos = await asyncio.to_thread(
            ss.butter, order, cutoff_hz, btype=btype_map[band_type], fs=fs, output="sos"
        )
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:butter-{band_type}",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
