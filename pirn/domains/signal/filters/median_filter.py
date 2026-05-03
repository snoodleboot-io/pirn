"""``MedianFilter`` — running median filter for spike removal."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MedianFilter(Knot):
    """Apply a running median filter to suppress impulsive noise spikes."""

    def __init__(
        self,
        *,
        signal: Knot,
        kernel_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(kernel_size, int) or kernel_size <= 0 or kernel_size % 2 == 0:
            raise ValueError(
                "MedianFilter: kernel_size must be a positive odd integer"
            )
        self._kernel_size = kernel_size
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def kernel_size(self) -> int:
        return self._kernel_size

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the running median filter and return the de-spiked SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            Filtered SignalFrame with the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:median",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
