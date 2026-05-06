"""``EpochExtractor`` — extract event-locked epochs from a signal.

Production version uses ``mne.Epochs``. This stub validates inputs and
returns a tuple of one :class:`SignalFrame` per supplied event.

Algorithm:
    1. Receive a SignalFrame, event_times_sec sequence, tmin_sec, and tmax_sec.
    2. Validate types and that tmin_sec < tmax_sec.
    3. For each event time, slice the signal from tmin_sec to tmax_sec relative to the event.
    4. Return each slice as a SignalFrame in a tuple.

Math:
    $$n_{\\text{samples}} = \\text{round}((t_{\\max} - t_{\\min}) \\times f_s)$$

References:
    - MNE Epochs: https://mne.tools/stable/generated/mne.Epochs.html
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
        signal: Knot | SignalFrame,
        event_times_sec: Knot | Sequence[float],
        tmin_sec: Knot | float,
        tmax_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            event_times_sec=event_times_sec,
            tmin_sec=tmin_sec,
            tmax_sec=tmax_sec,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        event_times_sec: Sequence[float],
        tmin_sec: float,
        tmax_sec: float,
        **_: Any,
    ) -> tuple[SignalFrame, ...]:
        """Slice the signal around each event time and return one SignalFrame per epoch.

        Args:
            signal: The continuous SignalFrame to slice.
            event_times_sec: Sequence of event onset times in seconds.
            tmin_sec: Start time relative to event in seconds.
            tmax_sec: End time relative to event in seconds (must exceed tmin_sec).

        Returns:
            A tuple of SignalFrames, one per event time, each spanning tmin_sec to tmax_sec.

        Raises:
            TypeError: If signal is not SignalFrame or event_times_sec is not list/tuple of numbers.
            ValueError: If tmin_sec >= tmax_sec.
        """
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
        # Production: slice the underlying ndarray around each event time.
        epoch_samples = max(
            1,
            int(round((float(tmax_sec) - float(tmin_sec)) * signal.sample_rate_hz)),
        )
        return tuple(
            SignalFrame(
                signal_id=f"{signal.signal_id}-epoch-{idx}",
                channel_count=signal.channel_count,
                sample_rate_hz=signal.sample_rate_hz,
                samples_per_channel=epoch_samples,
                fetched_at=signal.fetched_at,
            )
            for idx in range(len(event_times_sec))
        )
