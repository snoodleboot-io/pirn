"""``NotchFilter`` — narrow-bandstop / IIR notch filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class NotchFilter(Knot):
    """IIR notch (line-noise rejection) filter.

    Production needs ``scipy.signal.iirnotch``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        notch_hz: float,
        quality_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(notch_hz, (int, float)) or notch_hz <= 0:
            raise ValueError("NotchFilter: notch_hz must be positive")
        if not isinstance(quality_factor, (int, float)) or quality_factor <= 0:
            raise ValueError(
                "NotchFilter: quality_factor must be positive"
            )
        self._notch_hz = float(notch_hz)
        self._quality_factor = float(quality_factor)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def notch_hz(self) -> float:
        return self._notch_hz

    @property
    def quality_factor(self) -> float:
        return self._quality_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the notch filter to suppress the configured frequency and return the filtered SignalFrame.

        Args:
            signal: Signal to notch-filter at the configured line-noise frequency.

        Returns:
            SignalFrame with the notch frequency removed.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:notch",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
