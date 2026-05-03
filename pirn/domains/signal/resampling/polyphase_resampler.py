"""``PolyphaseResampler`` — polyphase rate-conversion filter bank."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PolyphaseResampler(Knot):
    """Polyphase resampler at integer L/M ratio with anti-alias FIR.

    Production needs ``scipy.signal.upfirdn`` or ``resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: int,
        downsample_factor: int,
        filter_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(upsample_factor, int) or upsample_factor <= 0:
            raise ValueError(
                "PolyphaseResampler: upsample_factor must be a positive integer"
            )
        if not isinstance(downsample_factor, int) or downsample_factor <= 0:
            raise ValueError(
                "PolyphaseResampler: downsample_factor must be a positive integer"
            )
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "PolyphaseResampler: filter_length must be a positive integer"
            )
        self._upsample_factor = upsample_factor
        self._downsample_factor = downsample_factor
        self._filter_length = filter_length
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def upsample_factor(self) -> int:
        return self._upsample_factor

    @property
    def downsample_factor(self) -> int:
        return self._downsample_factor

    @property
    def filter_length(self) -> int:
        return self._filter_length

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Resample the signal at the configured L/M integer ratio and return the polyphase-resampled SignalFrame.

        Args:
            signal: Signal to resample using the polyphase filter bank.

        Returns:
            SignalFrame at the new sample rate computed as ``fs * upsample_factor / downsample_factor``.
        """
        new_rate = (
            signal.sample_rate_hz * self._upsample_factor
        ) / self._downsample_factor
        new_samples = (
            signal.samples_per_channel * self._upsample_factor
        ) // self._downsample_factor
        return SignalFrame(
            signal_id=f"{signal.signal_id}:polyphase",
            channel_count=signal.channel_count,
            sample_rate_hz=new_rate,
            samples_per_channel=new_samples,
        )
