"""``Downsampler`` — drop samples (no filter)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Downsampler(Knot):
    """Keep every Nth sample (caller is responsible for anti-aliasing).

    Production needs ``numpy`` indexing only.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        downsample_factor: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(downsample_factor, int) or downsample_factor <= 1:
            raise ValueError(
                "Downsampler: downsample_factor must be an integer > 1"
            )
        self._downsample_factor = downsample_factor
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def downsample_factor(self) -> int:
        return self._downsample_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:downsample",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz / self._downsample_factor,
            samples_per_channel=signal.samples_per_channel
            // self._downsample_factor,
        )
