"""``ArbitraryResamplerPipeline`` — resample to any target rate via polyphase rational resampling."""

from __future__ import annotations

from math import gcd
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ArbitraryResamplerPipeline(Knot):
    """Resample from any input rate to any output rate using polyphase rational resampling.

    Production needs ``scipy.signal.resample_poly``.
    """

    _PRECISION: int = 1000

    def __init__(
        self,
        *,
        signal: Knot,
        input_rate_hz: float,
        output_rate_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(input_rate_hz, (int, float)) or input_rate_hz <= 0:
            raise ValueError(
                "ArbitraryResamplerPipeline: input_rate_hz must be positive"
            )
        if not isinstance(output_rate_hz, (int, float)) or output_rate_hz <= 0:
            raise ValueError(
                "ArbitraryResamplerPipeline: output_rate_hz must be positive"
            )
        self._input_rate_hz = float(input_rate_hz)
        self._output_rate_hz = float(output_rate_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def input_rate_hz(self) -> float:
        return self._input_rate_hz

    @property
    def output_rate_hz(self) -> float:
        return self._output_rate_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Resample the signal from the input rate to the output rate and return the resampled SignalFrame.

        Args:
            signal: Signal to resample.

        Returns:
            SignalFrame at ``output_rate_hz`` with sample count scaled proportionally.
        """
        ratio = self._output_rate_hz / self._input_rate_hz
        new_samples = int(signal.samples_per_channel * ratio)
        return SignalFrame(
            signal_id=f"{signal.signal_id}:resampled",
            channel_count=signal.channel_count,
            sample_rate_hz=self._output_rate_hz,
            samples_per_channel=new_samples,
        )
