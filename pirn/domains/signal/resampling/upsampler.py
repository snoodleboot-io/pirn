"""``Upsampler`` — zero-stuff upsample (no filter)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Upsampler(Knot):
    """Insert zeros between samples by an integer factor.

    Production needs ``numpy`` for the zero-stuffing step.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(upsample_factor, int) or upsample_factor <= 1:
            raise ValueError(
                "Upsampler: upsample_factor must be an integer > 1"
            )
        self._upsample_factor = upsample_factor
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def upsample_factor(self) -> int:
        return self._upsample_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Zero-stuff the signal by the configured integer factor and return the upsampled SignalFrame.

        Args:
            signal: Signal to upsample by inserting zeros between each sample.

        Returns:
            SignalFrame at the higher sample rate with zeros inserted between original samples.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:upsample",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz * self._upsample_factor,
            samples_per_channel=signal.samples_per_channel
            * self._upsample_factor,
        )
