"""``RationalResamplerPipeline`` — upsample / filter / downsample at a ratio."""

from __future__ import annotations

from math import gcd
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class RationalResamplerPipeline(Knot):
    """Rational sample-rate conversion at ratio L/M.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        upsample_factor: int,
        downsample_factor: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(upsample_factor, int) or upsample_factor <= 0:
            raise ValueError(
                "RationalResamplerPipeline: upsample_factor must be a positive integer"
            )
        if not isinstance(downsample_factor, int) or downsample_factor <= 0:
            raise ValueError(
                "RationalResamplerPipeline: downsample_factor must be a positive integer"
            )
        common = gcd(upsample_factor, downsample_factor)
        self._upsample_factor = upsample_factor // common
        self._downsample_factor = downsample_factor // common
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def upsample_factor(self) -> int:
        return self._upsample_factor

    @property
    def downsample_factor(self) -> int:
        return self._downsample_factor

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        new_rate = (
            signal.sample_rate_hz * self._upsample_factor
        ) / self._downsample_factor
        new_samples = (
            signal.samples_per_channel * self._upsample_factor
        ) // self._downsample_factor
        return SignalFrame(
            signal_id=f"{signal.signal_id}:rational",
            channel_count=signal.channel_count,
            sample_rate_hz=new_rate,
            samples_per_channel=new_samples,
        )
