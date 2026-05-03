"""``ClockDriftCorrector`` — compensate for clock drift between synchronized sources."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ClockDriftCorrector(Knot):
    """Compensate for clock drift by resampling to the reference rate.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        reference_rate_hz: float,
        measured_rate_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(reference_rate_hz, (int, float)) or reference_rate_hz <= 0:
            raise ValueError(
                "ClockDriftCorrector: reference_rate_hz must be positive"
            )
        if not isinstance(measured_rate_hz, (int, float)) or measured_rate_hz <= 0:
            raise ValueError(
                "ClockDriftCorrector: measured_rate_hz must be positive"
            )
        self._reference_rate_hz = float(reference_rate_hz)
        self._measured_rate_hz = float(measured_rate_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def reference_rate_hz(self) -> float:
        return self._reference_rate_hz

    @property
    def measured_rate_hz(self) -> float:
        return self._measured_rate_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Correct clock drift by resampling from the measured rate to the reference rate.

        Args:
            signal: Signal captured at the drifted measured rate.

        Returns:
            SignalFrame resampled to the reference rate with drift corrected.
        """
        ratio = self._reference_rate_hz / self._measured_rate_hz
        new_samples = int(signal.samples_per_channel * ratio)
        return SignalFrame(
            signal_id=f"{signal.signal_id}:drift_corrected",
            channel_count=signal.channel_count,
            sample_rate_hz=self._reference_rate_hz,
            samples_per_channel=new_samples,
        )
