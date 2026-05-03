"""``LMSAdaptiveFilter`` — least-mean-squares adaptive filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class LMSAdaptiveFilter(Knot):
    """Stochastic-gradient LMS adaptive filter.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: int,
        step_size: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "LMSAdaptiveFilter: filter_length must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError(
                "LMSAdaptiveFilter: step_size must be positive"
            )
        self._filter_length = filter_length
        self._step_size = float(step_size)
        super().__init__(
            signal=signal, reference=reference, _config=_config, **kwargs
        )

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def step_size(self) -> float:
        return self._step_size

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Adapt the LMS filter weights against the reference and return the error-minimised SignalFrame.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to compute the error and update filter weights.

        Returns:
            SignalFrame of the LMS-filtered output.

        Raises:
            ValueError: If signal and reference have different sample rates.
        """
        if signal.sample_rate_hz != reference.sample_rate_hz:
            raise ValueError(
                "LMSAdaptiveFilter: signal and reference sample rates must match"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:lms",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
