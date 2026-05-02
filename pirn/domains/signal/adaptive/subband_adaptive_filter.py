"""``SubbandAdaptiveFilter`` — subband-decomposition adaptive filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SubbandAdaptiveFilter(Knot):
    """Subband adaptive filter — decompose, adapt per band, reconstruct.

    Production needs an analysis/synthesis filter bank plus an inner
    adaptive filter such as NLMS.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        subband_count: int,
        filter_length_per_band: int,
        step_size: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(subband_count, int) or subband_count <= 1:
            raise ValueError(
                "SubbandAdaptiveFilter: subband_count must be an integer > 1"
            )
        if (
            not isinstance(filter_length_per_band, int)
            or filter_length_per_band <= 0
        ):
            raise ValueError(
                "SubbandAdaptiveFilter: filter_length_per_band must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError(
                "SubbandAdaptiveFilter: step_size must be positive"
            )
        self._subband_count = subband_count
        self._filter_length_per_band = filter_length_per_band
        self._step_size = float(step_size)
        super().__init__(
            signal=signal, reference=reference, _config=_config, **kwargs
        )

    @property
    def subband_count(self) -> int:
        return self._subband_count

    @property
    def filter_length_per_band(self) -> int:
        return self._filter_length_per_band

    @property
    def step_size(self) -> float:
        return self._step_size

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:subband-adaptive",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
