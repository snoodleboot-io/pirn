"""``RLSAdaptiveFilter`` — recursive least squares adaptive filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class RLSAdaptiveFilter(Knot):
    """Exponentially-weighted RLS adaptive filter.

    Production needs ``padasip`` or hand-rolled NumPy.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: int,
        forgetting_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "RLSAdaptiveFilter: filter_length must be a positive integer"
            )
        if (
            not isinstance(forgetting_factor, (int, float))
            or not 0.0 < forgetting_factor <= 1.0
        ):
            raise ValueError(
                "RLSAdaptiveFilter: forgetting_factor must lie in (0, 1]"
            )
        self._filter_length = filter_length
        self._forgetting_factor = float(forgetting_factor)
        super().__init__(
            signal=signal, reference=reference, _config=_config, **kwargs
        )

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def forgetting_factor(self) -> float:
        return self._forgetting_factor

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:rls",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
