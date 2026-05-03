"""``EchoCanceller`` — acoustic echo cancellation."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class EchoCanceller(Knot):
    """Acoustic echo canceller using LMS adaptive filtering.

    Production needs an adaptive-filtering library (``padasip``) or a
    hand-rolled NumPy implementation.
    """

    def __init__(
        self,
        *,
        microphone: Knot,
        far_end: Knot,
        filter_length: int,
        step_size: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(filter_length, int) or filter_length <= 0:
            raise ValueError(
                "EchoCanceller: filter_length must be a positive integer"
            )
        if not isinstance(step_size, (int, float)) or step_size <= 0 or step_size > 1:
            raise ValueError(
                "EchoCanceller: step_size must be in range (0, 1]"
            )
        self._filter_length = filter_length
        self._step_size = float(step_size)
        super().__init__(microphone=microphone, far_end=far_end, _config=_config, **kwargs)

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def step_size(self) -> float:
        return self._step_size

    async def process(
        self,
        microphone: SignalFrame,
        far_end: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Remove acoustic echo from the microphone signal using the far-end reference.

        Args:
            microphone: Near-end microphone signal containing speech plus echo.
            far_end: Far-end reference signal used to model the echo path.

        Returns:
            SignalFrame with the estimated echo removed.

        Raises:
            ValueError: If microphone and far_end have different sample rates.
        """
        if microphone.sample_rate_hz != far_end.sample_rate_hz:
            raise ValueError(
                "EchoCanceller: microphone and far_end sample rates must match"
            )
        return SignalFrame(
            signal_id=f"{microphone.signal_id}:echo_cancelled",
            channel_count=microphone.channel_count,
            sample_rate_hz=microphone.sample_rate_hz,
            samples_per_channel=microphone.samples_per_channel,
        )
