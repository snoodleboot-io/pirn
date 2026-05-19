"""``FIRWindowFilter`` — FIR filter designed via the window method.

Algorithm:
    1. Receive the input signal payload, num_taps, cutoff_hz, and window.
    2. Validate num_taps (positive odd integer), cutoff_hz (positive), and window name.
    3. Design FIR coefficients using ``scipy.signal.firwin``.
    4. Apply via ``scipy.signal.lfilter(h, [1.0], data)``.
    5. Return a filtered SignalPayload.

References:
    - scipy.signal.firwin: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.firwin.html
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


class FIRWindowFilter(Knot):
    """Window-method FIR filter."""

    _valid_windows: ClassVar[frozenset[str]] = frozenset(
        {"hamming", "hann", "blackman", "kaiser", "flattop"}
    )

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
        signal: SignalPayload,
        num_taps: int,
        cutoff_hz: float,
        window: str,
        **_: Any,
    ) -> SignalPayload:
        """Apply the window-method FIR filter and return the filtered SignalPayload.

        Args:
            signal: The input signal payload.
            num_taps: Number of filter taps (positive odd integer).
            cutoff_hz: Cutoff frequency in Hz (positive float).
            window: Window function name: ``hamming``, ``hann``, ``blackman``,
                ``bartlett``, ``kaiser``, ``flattop``.

        Returns:
            SignalPayload filtered with the window-designed FIR.

        Raises:
            ValueError: If num_taps, cutoff_hz, or window are invalid.
        """
        if not isinstance(num_taps, int) or num_taps <= 0 or num_taps % 2 == 0:
            raise ValueError("FIRWindowFilter: num_taps must be a positive odd integer")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("FIRWindowFilter: cutoff_hz must be a positive scalar")
        if window not in self._valid_windows:
            raise ValueError(
                f"FIRWindowFilter: window must be one of {sorted(self._valid_windows)}"
            )

        tap_weights = await asyncio.to_thread(
            ss.firwin, num_taps, cutoff_hz, window=window, fs=signal.frame.sample_rate_hz
        )
        filtered = await asyncio.to_thread(
            ss.lfilter, tap_weights, np.array([1.0]), signal.data, axis=-1
        )

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:fir-window",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.frame.samples_per_channel,
            ),
            data=np.asarray(filtered),
        )
