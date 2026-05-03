"""``Decimator`` — anti-alias filter then integer downsample."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Decimator(Knot):
    """Decimate by an integer factor.

    Production needs ``scipy.signal.decimate``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        decimation_factor: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(decimation_factor, int) or decimation_factor <= 1:
            raise ValueError(
                "Decimator: decimation_factor must be an integer > 1"
            )
        self._decimation_factor = decimation_factor
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def decimation_factor(self) -> int:
        return self._decimation_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Anti-alias filter and decimate the signal by the configured integer factor.

        Args:
            signal: Signal to anti-alias filter and downsample.

        Returns:
            SignalFrame at the reduced sample rate with a proportionally smaller sample count.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:decimate",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz / self._decimation_factor,
            samples_per_channel=signal.samples_per_channel
            // self._decimation_factor,
        )
