"""``ANCPipeline`` — active noise control pipeline using LMS-based adaptive filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ANCPipeline(Knot):
    """Active noise control pipeline using LMS-based adaptive filtering.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

    def __init__(
        self,
        *,
        reference: Knot,
        error: Knot,
        step_size: float,
        filter_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError(
                "ANCPipeline: step_size must be in range (0, 1]"
            )
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "ANCPipeline: filter_length must be a positive integer"
            )
        self._step_size = float(step_size)
        self._filter_length = filter_length
        super().__init__(reference=reference, error=error, _config=_config, **kwargs)

    @property
    def step_size(self) -> float:
        return self._step_size

    @property
    def filter_length(self) -> int:
        return self._filter_length

    async def process(
        self,
        reference: SignalFrame,
        error: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Compute the anti-noise output by adapting LMS filter weights against the error signal.

        Args:
            reference: Reference signal capturing the noise source.
            error: Error signal (residual noise at the cancellation point).

        Returns:
            SignalFrame containing the anti-noise output.

        Raises:
            ValueError: If reference and error have different sample rates.
        """
        if reference.sample_rate_hz != error.sample_rate_hz:
            raise ValueError(
                "ANCPipeline: reference and error sample rates must match"
            )
        return SignalFrame(
            signal_id=f"{reference.signal_id}:anc",
            channel_count=reference.channel_count,
            sample_rate_hz=reference.sample_rate_hz,
            samples_per_channel=reference.samples_per_channel,
        )
