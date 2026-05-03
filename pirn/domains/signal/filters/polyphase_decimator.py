"""``PolyphaseDecimator`` — efficient downsampling via polyphase FIR."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PolyphaseDecimator(Knot):
    """Polyphase FIR decimator (anti-alias filter + downsample).

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        decimation_factor: int,
        filter_taps: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(decimation_factor, int) or decimation_factor <= 1:
            raise ValueError(
                "PolyphaseDecimator: decimation_factor must be an integer > 1"
            )
        if not isinstance(filter_taps, int) or filter_taps <= 0:
            raise ValueError(
                "PolyphaseDecimator: filter_taps must be a positive integer"
            )
        self._decimation_factor = decimation_factor
        self._filter_taps = filter_taps
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def decimation_factor(self) -> int:
        return self._decimation_factor

    @property
    def filter_taps(self) -> int:
        return self._filter_taps

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Anti-alias filter and downsample the input signal by the configured factor and return the decimated SignalFrame.

        Args:
            signal: Signal to anti-alias filter and downsample.

        Returns:
            SignalFrame at the reduced sample rate with a proportionally smaller sample count.
        """
        new_rate = signal.sample_rate_hz / self._decimation_factor
        new_samples = signal.samples_per_channel // self._decimation_factor
        return SignalFrame(
            signal_id=f"{signal.signal_id}:polyphase-dec",
            channel_count=signal.channel_count,
            sample_rate_hz=new_rate,
            samples_per_channel=new_samples,
        )
