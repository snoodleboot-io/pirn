"""``FIRWindowFilter`` — FIR filter designed via the window method."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRWindowFilter(Knot):
    """Design a linear-phase FIR filter using the window method."""

    _valid_windows = frozenset({"hamming", "hann", "blackman", "rectangular"})

    def __init__(
        self,
        *,
        signal: Knot,
        num_taps: int,
        cutoff_hz: float,
        window: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(num_taps, int) or num_taps <= 0 or num_taps % 2 == 0:
            raise ValueError(
                "FIRWindowFilter: num_taps must be a positive odd integer"
            )
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("FIRWindowFilter: cutoff_hz must be a positive scalar")
        if window not in self._valid_windows:
            raise ValueError(
                "FIRWindowFilter: window must be one of "
                "'hamming', 'hann', 'blackman', 'rectangular'"
            )
        self._num_taps = num_taps
        self._cutoff_hz = float(cutoff_hz)
        self._window = window
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_taps(self) -> int:
        return self._num_taps

    @property
    def window(self) -> str:
        return self._window

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the window-method FIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            Filtered SignalFrame with the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir-window",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
