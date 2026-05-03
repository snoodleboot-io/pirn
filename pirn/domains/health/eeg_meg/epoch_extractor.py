"""``EpochExtractor`` — extract event-locked epochs from a signal.

Production version uses ``mne.Epochs``. This stub validates inputs and
returns a tuple of one :class:`SignalFrame` per supplied event.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class EpochExtractor(Knot):
    """Extract event-locked epochs from a continuous signal."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        event_times_sec: Sequence[float],
        tmin_sec: float,
        tmax_sec: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("EpochExtractor: signal must be a SignalFrame")
        if not isinstance(event_times_sec, (list, tuple)):
            raise TypeError(
                "EpochExtractor: event_times_sec must be list/tuple"
            )
        for t in event_times_sec:
            if not isinstance(t, (int, float)):
                raise TypeError(
                    "EpochExtractor: every event time must be numeric"
                )
        if not isinstance(tmin_sec, (int, float)):
            raise TypeError("EpochExtractor: tmin_sec must be numeric")
        if not isinstance(tmax_sec, (int, float)):
            raise TypeError("EpochExtractor: tmax_sec must be numeric")
        if float(tmin_sec) >= float(tmax_sec):
            raise ValueError(
                "EpochExtractor: tmin_sec must be < tmax_sec"
            )
        self._signal = signal
        self._event_times = tuple(float(t) for t in event_times_sec)
        self._tmin = float(tmin_sec)
        self._tmax = float(tmax_sec)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[SignalFrame, ...]:
        """Slice the signal around each event time and return one SignalFrame per epoch.

        Returns:
            A tuple of SignalFrames, one per event time, each spanning tmin_sec to tmax_sec.
        """
        # Production: slice the underlying ndarray around each event time.
        epoch_samples = max(
            1,
            int(round((self._tmax - self._tmin) * self._signal.sample_rate_hz)),
        )
        return tuple(
            SignalFrame(
                signal_id=f"{self._signal.signal_id}-epoch-{idx}",
                channel_count=self._signal.channel_count,
                sample_rate_hz=self._signal.sample_rate_hz,
                samples_per_channel=epoch_samples,
                fetched_at=self._signal.fetched_at,
            )
            for idx in range(len(self._event_times))
        )
