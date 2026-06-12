"""``EpochExtractor`` — extract event-locked epochs from a signal.

Algorithm:
    1. Receive a HealthSignalPayload, event_times_sec sequence, tmin_sec, and tmax_sec.
    2. Validate types and that tmin_sec < tmax_sec.
    3. For each event time, slice signal.data from tmin_sec to tmax_sec relative to the event.
    4. Return each slice as a HealthSignalPayload in a tuple.

Math:
    $$n_{\\text{samples}} = \\text{round}((t_{\\max} - t_{\\min}) \\times f_s)$$

References:
    - MNE Epochs: https://mne.tools/stable/generated/mne.Epochs.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload


def _extract_epochs(
    data: np.ndarray,
    fs: float,
    event_times: Sequence[float],
    tmin: float,
    tmax: float,
) -> list[np.ndarray]:
    """Slice data around each event time and return a list of epoch arrays."""
    n_samples = data.shape[-1]
    epochs: list[np.ndarray] = []
    for t in event_times:
        start = max(0, round((t + tmin) * fs))
        end = min(n_samples, round((t + tmax) * fs))
        epochs.append(data[..., start:end])
    return epochs


class EpochExtractor(Knot):
    """Extract event-locked epochs from a continuous signal."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
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
        signal: HealthSignalPayload,
        event_times_sec: Sequence[float],
        tmin_sec: float,
        tmax_sec: float,
        **_: Any,
    ) -> tuple[HealthSignalPayload, ...]:
        """Slice the signal around each event time and return one HealthSignalPayload per epoch.

        Args:
            signal: The continuous HealthSignalPayload to slice.
            event_times_sec: Sequence of event onset times in seconds.
            tmin_sec: Start time relative to event in seconds.
            tmax_sec: End time relative to event in seconds (must exceed tmin_sec).

        Returns:
            A tuple of SignalPayloads, one per event time, each spanning tmin_sec to tmax_sec.

        Raises:
            TypeError: If signal is not HealthSignalPayload or event_times_sec is not list/tuple of numbers.
            ValueError: If tmin_sec >= tmax_sec.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("EpochExtractor: signal must be a HealthSignalPayload")
        if not isinstance(event_times_sec, (list, tuple)):
            raise TypeError("EpochExtractor: event_times_sec must be list/tuple")
        for t in event_times_sec:
            if not isinstance(t, (int, float)):
                raise TypeError("EpochExtractor: every event time must be numeric")
        if not isinstance(tmin_sec, (int, float)):
            raise TypeError("EpochExtractor: tmin_sec must be numeric")
        if not isinstance(tmax_sec, (int, float)):
            raise TypeError("EpochExtractor: tmax_sec must be numeric")
        if float(tmin_sec) >= float(tmax_sec):
            raise ValueError("EpochExtractor: tmin_sec must be < tmax_sec")

        fs = signal.frame.sample_rate_hz
        arrays = await asyncio.to_thread(
            _extract_epochs, signal.data, fs, event_times_sec, float(tmin_sec), float(tmax_sec)
        )
        result: list[HealthSignalPayload] = []
        for idx, arr in enumerate(arrays):
            epoch_samples = arr.shape[-1]
            frame = HealthSignalFrame(
                signal_id=f"{signal.frame.signal_id}-epoch-{idx}",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=fs,
                samples_per_channel=epoch_samples,
                fetched_at=signal.frame.fetched_at,
            )
            result.append(HealthSignalPayload(metadata=frame, data=arr))
        return tuple(result)
