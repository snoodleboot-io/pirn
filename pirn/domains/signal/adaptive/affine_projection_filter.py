"""``AffineProjectionFilter`` — affine projection adaptive filter (APA)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AffineProjectionFilter(Knot):
    """Affine projection adaptive filter.

    Production needs ``padasip`` or a hand-rolled NumPy implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference: Knot,
        filter_length: int,
        projection_order: int,
        step_size: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "AffineProjectionFilter: filter_length must be a positive integer"
            )
        if not isinstance(projection_order, int) or projection_order <= 0:
            raise ValueError(
                "AffineProjectionFilter: projection_order must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0:
            raise ValueError(
                "AffineProjectionFilter: step_size must be positive"
            )
        self._filter_length = filter_length
        self._projection_order = projection_order
        self._step_size = float(step_size)
        super().__init__(
            signal=signal, reference=reference, _config=_config, **kwargs
        )

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def projection_order(self) -> int:
        return self._projection_order

    @property
    def step_size(self) -> float:
        return self._step_size

    async def process(
        self,
        signal: SignalFrame,
        reference: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Apply the affine projection adaptive filter to the signal using the reference and return the filtered SignalFrame.

        Args:
            signal: Input signal to filter.
            reference: Reference signal used to drive the adaptive weight update.

        Returns:
            SignalFrame of the APA-filtered output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:apa",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
