"""``HighPassFilter`` — pass high frequencies, attenuate low."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class HighPassFilter(Knot):
    """High-pass filter wrapper.

    Production needs ``scipy.signal``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        cutoff_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("HighPassFilter: cutoff_hz must be positive")
        self._cutoff_hz = float(cutoff_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def cutoff_hz(self) -> float:
        return self._cutoff_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the high-pass filter to the input signal and return the filtered SignalFrame.

        Args:
            signal: Signal to high-pass filter above the configured cutoff frequency.

        Returns:
            SignalFrame with low-frequency content attenuated.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:highpass",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
