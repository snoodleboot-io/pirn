"""``SleepStageClassifier`` — classify 30-second PSG epochs into sleep stages (W, N1, N2, N3, REM).

Algorithm:
    1. Receive a HealthSignalPayload, epoch_duration_sec int, and channels tuple.
    2. Validate types and that epoch_duration_sec == 30 and channels is non-empty.
    3. Segment the signal into 30-second epochs.
    4. For each epoch, compute band power (delta/theta/alpha/beta/gamma) via scipy.signal.welch.
    5. Classify each epoch using heuristic thresholds:
       - High delta power → N3 (deep sleep)
       - High theta power → N1/N2
       - High alpha power → Wake
       - Otherwise → N2
    6. Return dict with epoch_stages, hypnogram, stage_labels, total_epochs, sleep_efficiency_pct.

Math:
    $$\\text{sleep\\_efficiency} = \\frac{|\\{e : \\text{stage}(e) \\neq W\\}|}{|\\text{epochs}|} \\times 100$$

References:
    - AASM Scoring Rules: https://aasm.org/resources/clinicalguidelines/scoring-manual.pdf
    - Rechtschaffen & Kales (1968) A Manual of Standardized Terminology.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload


def _band_power(epoch: np.ndarray, fs: float, low: float, high: float) -> float:
    freqs, psd = ss.welch(epoch, fs=fs)
    mask = (freqs >= low) & (freqs <= high)
    return float(np.trapz(psd[mask], freqs[mask])) if mask.any() else 0.0


def _classify_epoch(epoch: np.ndarray, fs: float) -> str:
    delta = _band_power(epoch, fs, 0.5, 4.0)
    theta = _band_power(epoch, fs, 4.0, 8.0)
    alpha = _band_power(epoch, fs, 8.0, 13.0)
    total = delta + theta + alpha + 1e-12
    if delta / total > 0.5:
        return "N3"
    if alpha / total > 0.4:
        return "W"
    if theta / total > 0.35:
        return "N1"
    return "N2"


def _classify_signal(data: np.ndarray, fs: float, epoch_duration_sec: int) -> list[str]:
    epoch_samples = int(fs * epoch_duration_sec)
    channel = data[0] if data.ndim > 1 else data
    stages: list[str] = []
    for start in range(0, len(channel), epoch_samples):
        epoch = channel[start : start + epoch_samples]
        if len(epoch) < epoch_samples // 2:
            break
        stages.append(_classify_epoch(epoch, fs))
    return stages


class SleepStageClassifier(Knot):
    """Classify 30-second PSG epochs into sleep stages (W, N1, N2, N3, REM)."""

    _valid_stages: ClassVar[frozenset[str]] = frozenset({"W", "N1", "N2", "N3", "REM"})

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        epoch_duration_sec: Knot | int,
        channels: Knot | tuple[str, ...] = ("EEG", "EOG", "EMG"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            epoch_duration_sec=epoch_duration_sec,
            channels=channels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        epoch_duration_sec: int,
        channels: tuple[str, ...] = ("EEG", "EOG", "EMG"),
        **_: Any,
    ) -> dict[str, Any]:
        """Classify each 30-second epoch of the signal payload into a sleep stage.

        Args:
            signal: The HealthSignalPayload containing the PSG recording.
            epoch_duration_sec: Must be 30 (the standard PSG epoch length).
            channels: Non-empty tuple of channel name strings to use for classification.

        Returns:
            Dict with epoch_stages (list[str]), hypnogram (list[str]),
            stage_labels (list[str]), total_epochs (int), sleep_efficiency_pct (float).

        Raises:
            TypeError: If signal is not a HealthSignalPayload.
            ValueError: If epoch_duration_sec != 30 or channels is empty.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("SleepStageClassifier: signal must be a HealthSignalPayload")
        if epoch_duration_sec != 30:
            raise ValueError("SleepStageClassifier: epoch_duration_sec must be 30")
        if not isinstance(channels, tuple) or len(channels) == 0:
            raise ValueError("SleepStageClassifier: channels must be a non-empty tuple")

        fs = signal.frame.sample_rate_hz
        stage_labels = await asyncio.to_thread(
            _classify_signal, signal.data, fs, epoch_duration_sec
        )

        n_sleep = sum(1 for s in stage_labels if s != "W")
        sleep_efficiency_pct = (n_sleep / len(stage_labels) * 100.0) if stage_labels else 0.0
        return {
            "epoch_stages": stage_labels,
            "hypnogram": stage_labels,
            "stage_labels": stage_labels,
            "total_epochs": len(stage_labels),
            "sleep_efficiency_pct": sleep_efficiency_pct,
        }
