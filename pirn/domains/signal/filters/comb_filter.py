"""``CombFilter`` — feedforward/feedback comb filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class CombFilter(Knot):
    """Apply a comb filter with a fixed delay and gain coefficient."""

    def __init__(
        self,
        *,
        signal: Knot,
        delay_samples: int,
        gain: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(delay_samples, int) or delay_samples <= 0:
            raise ValueError("CombFilter: delay_samples must be a positive integer")
        if not isinstance(gain, (int, float)) or not (0.0 <= gain <= 1.0):
            raise ValueError("CombFilter: gain must be a float in [0.0, 1.0]")
        self._delay_samples = delay_samples
        self._gain = float(gain)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def delay_samples(self) -> int:
        return self._delay_samples

    @property
    def gain(self) -> float:
        return self._gain

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the comb filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            Filtered SignalFrame with the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:comb",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
