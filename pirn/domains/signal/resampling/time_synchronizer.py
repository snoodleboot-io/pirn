"""``TimeSynchronizer`` — align two signals via cross-correlation time offset estimation."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class TimeSynchronizer(Knot):
    """Align two signals in time by estimating the offset via cross-correlation.

    Production needs ``scipy.signal.correlate``.
    """

    def __init__(
        self,
        *,
        reference: Knot,
        target: Knot,
        max_lag_samples: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_lag_samples, int) or max_lag_samples <= 0:
            raise ValueError(
                "TimeSynchronizer: max_lag_samples must be a positive integer"
            )
        self._max_lag_samples = max_lag_samples
        super().__init__(reference=reference, target=target, _config=_config, **kwargs)

    @property
    def max_lag_samples(self) -> int:
        return self._max_lag_samples

    async def process(
        self,
        reference: SignalFrame,
        target: SignalFrame,
        **_: Any,
    ) -> SignalFrame:
        """Estimate the time offset between reference and target via cross-correlation and return the aligned target.

        Args:
            reference: Reference signal defining the time base.
            target: Target signal to align to the reference.

        Returns:
            SignalFrame of the target signal shifted to align with the reference.
        """
        return SignalFrame(
            signal_id=f"{target.signal_id}:synced",
            channel_count=target.channel_count,
            sample_rate_hz=target.sample_rate_hz,
            samples_per_channel=target.samples_per_channel,
        )
