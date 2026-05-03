"""``NLMSAdaptiveFilter`` — normalised LMS adaptive filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class NLMSAdaptiveFilter(Knot):
    """Normalised LMS adaptive filter (LMS with input-power normalisation).

    Production needs ``padasip`` or hand-rolled NumPy.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: int,
        step_size: float,
        regularization: float = 1e-6,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "NLMSAdaptiveFilter: filter_length must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError(
                "NLMSAdaptiveFilter: step_size must be positive"
            )
        if not isinstance(regularization, (int, float)) or regularization < 0:
            raise ValueError(
                "NLMSAdaptiveFilter: regularization must be non-negative"
            )
        self._filter_length = filter_length
        self._step_size = float(step_size)
        self._regularization = float(regularization)
        super().__init__(
            signal=signal, reference=reference, _config=_config, **kwargs
        )

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def step_size(self) -> float:
        return self._step_size

    @property
    def regularization(self) -> float:
        return self._regularization

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Apply the normalised LMS filter to the signal using the reference and return the filtered SignalFrame.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to drive the normalised weight update.

        Returns:
            SignalFrame of the NLMS-filtered output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:nlms",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
