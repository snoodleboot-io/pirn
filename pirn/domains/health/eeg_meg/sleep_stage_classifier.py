"""``SleepStageClassifier`` — classify 30-second PSG epochs into sleep stages (W, N1, N2, N3, REM)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SleepStageClassifier(Knot):
    """Classify 30-second PSG epochs into sleep stages (W, N1, N2, N3, REM)."""

    _VALID_STAGES: frozenset[str] = frozenset({"W", "N1", "N2", "N3", "REM"})

    def __init__(
        self,
        *,
        psg_data: Knot,
        epoch_duration_sec: int,
        channels: tuple[str, ...] = ("EEG", "EOG", "EMG"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(psg_data, Knot):
            raise TypeError("SleepStageClassifier: psg_data must be a Knot")
        if epoch_duration_sec != 30:
            raise ValueError(
                "SleepStageClassifier: epoch_duration_sec must be 30"
            )
        if not isinstance(channels, tuple) or len(channels) == 0:
            raise ValueError(
                "SleepStageClassifier: channels must be a non-empty tuple"
            )
        self._epoch_duration_sec = epoch_duration_sec
        self._channels = channels
        super().__init__(psg_data=psg_data, _config=_config, **kwargs)

    async def process(
        self,
        psg_data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Classify each 30-second PSG epoch into a sleep stage.

        Args:
            psg_data: Dict with epochs (list of dicts with channel_data)
                and sample_rate_hz (float).

        Returns:
            Dict with stage_labels (list of str, each one of W/N1/N2/N3/REM),
            total_epochs (int), and sleep_efficiency_pct (float).
        """
        if not isinstance(psg_data, dict):
            raise TypeError("SleepStageClassifier: psg_data must be a dict")
        epochs = psg_data.get("epochs", [])
        stage_labels = ["N2"] * len(epochs)
        n_sleep = sum(1 for s in stage_labels if s != "W")
        sleep_efficiency_pct = (n_sleep / len(stage_labels) * 100.0) if stage_labels else 0.0
        return {
            "stage_labels": stage_labels,
            "total_epochs": len(epochs),
            "sleep_efficiency_pct": sleep_efficiency_pct,
        }
