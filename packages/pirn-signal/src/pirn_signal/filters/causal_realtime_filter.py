"""``CausalRealtimeFilter`` — causal (forward-only) IIR filter for realtime use.

Algorithm:
    1. Receive the input signal payload, filter_type, cutoff_hz, and order.
    2. Validate filter_type (known string), order (positive integer), and cutoff_hz
       (positive scalar or (low, high) tuple for band types).
    3. Design a Butterworth IIR filter of the given order and type.
    4. Apply causal forward filtering only (no backward pass) using ``sosfilt``.
    5. Return a filtered SignalPayload suitable for realtime processing.

Math:
    Causal IIR difference equation (direct form II):

    $$y(n) = \\sum_{k=0}^{M} b_k x(n-k) - \\sum_{k=1}^{N} a_k y(n-k)$$

    Unlike filtfilt, no phase reversal is applied. The phase response is non-zero
    but latency is bounded to the filter order.

References:
    - scipy.signal.sosfilt: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall.
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


class CausalRealtimeFilter(Knot):
    """Apply a causal IIR filter with no look-ahead, suitable for realtime processing."""

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
        signal: SignalPayload,
        filter_type: str,
        cutoff_hz: float | tuple[float, float],
        order: int,
        **_: Any,
    ) -> SignalPayload:
        """Apply the causal IIR filter and return the filtered SignalPayload.

        Args:
            signal: The input signal payload.
            filter_type: One of ``lowpass``, ``highpass``, ``bandpass``, ``bandstop``.
            cutoff_hz: Cutoff frequency or (low, high) pair in Hz.
            order: Filter order (positive integer).

        Returns:
            Filtered SignalPayload with the same shape as the input.

        Raises:
            ValueError: If filter_type, order, or cutoff_hz are invalid.
        """
        if filter_type not in {"lowpass", "highpass", "bandpass", "bandstop"}:
            raise ValueError(
                "CausalRealtimeFilter: filter_type must be one of "
                "'lowpass', 'highpass', 'bandpass', 'bandstop'"
            )
        if not isinstance(order, int) or order <= 0:
            raise ValueError("CausalRealtimeFilter: order must be a positive integer")
        if filter_type in {"bandpass", "bandstop"}:
            if (
                not isinstance(cutoff_hz, tuple)
                or len(cutoff_hz) != 2
                or any(not isinstance(c, (int, float)) for c in cutoff_hz)
            ):
                raise ValueError(
                    "CausalRealtimeFilter: bandpass/bandstop requires (low, high) tuple"
                )
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError("CausalRealtimeFilter: cutoff bounds must satisfy 0 < low < high")
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError("CausalRealtimeFilter: cutoff_hz must be a positive scalar")

        btype_map = {
            "lowpass": "low",
            "highpass": "high",
            "bandpass": "bandpass",
            "bandstop": "bandstop",
        }
        fs = signal.frame.sample_rate_hz
        sos = await asyncio.to_thread(
            ss.butter, order, cutoff_hz, btype=btype_map[filter_type], fs=fs, output="sos"
        )
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:causal-{filter_type}",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
