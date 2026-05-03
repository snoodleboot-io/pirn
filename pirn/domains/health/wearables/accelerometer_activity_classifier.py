"""``AccelerometerActivityClassifier`` — classify physical activity from tri-axial accelerometer data."""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AccelerometerActivityClassifier(Knot):
    """Classify physical activity from tri-axial accelerometer data."""

    def __init__(
        self,
        *,
        accel_data: Knot,
        sample_rate_hz: float,
        window_sec: float,
        activity_classes: tuple[str, ...] = ("sedentary", "light", "moderate", "vigorous"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(accel_data, Knot):
            raise TypeError(
                "AccelerometerActivityClassifier: accel_data must be a Knot"
            )
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError(
                "AccelerometerActivityClassifier: sample_rate_hz must be > 0"
            )
        if not isinstance(window_sec, (int, float)) or window_sec <= 0:
            raise ValueError(
                "AccelerometerActivityClassifier: window_sec must be > 0"
            )
        if not isinstance(activity_classes, tuple) or len(activity_classes) == 0:
            raise ValueError(
                "AccelerometerActivityClassifier: activity_classes must be a non-empty tuple"
            )
        self._sample_rate_hz = float(sample_rate_hz)
        self._window_sec = float(window_sec)
        self._activity_classes = activity_classes
        super().__init__(accel_data=accel_data, _config=_config, **kwargs)

    async def process(
        self,
        accel_data: dict[str, Any],
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Classify activity windows from tri-axial accelerometer readings.

        Args:
            accel_data: Dict with x (list of float), y (list of float),
                z (list of float), and timestamps_iso (list of str).

        Returns:
            List of dicts, each with start_iso, end_iso, activity_class,
            and vector_magnitude (float).
        """
        if not isinstance(accel_data, dict):
            raise TypeError(
                "AccelerometerActivityClassifier: accel_data must be a dict"
            )
        x = accel_data.get("x", [])
        y = accel_data.get("y", [])
        z = accel_data.get("z", [])
        timestamps = accel_data.get("timestamps_iso", [])
        window_samples = max(1, int(self._sample_rate_hz * self._window_sec))
        results: list[dict[str, Any]] = []
        n = len(timestamps)
        for start_idx in range(0, n, window_samples):
            end_idx = min(start_idx + window_samples, n)
            window_x = x[start_idx:end_idx]
            window_y = y[start_idx:end_idx]
            window_z = z[start_idx:end_idx]
            vm = 0.0
            if window_x and window_y and window_z:
                mean_x = sum(window_x) / len(window_x)
                mean_y = sum(window_y) / len(window_y)
                mean_z = sum(window_z) / len(window_z)
                vm = math.sqrt(mean_x ** 2 + mean_y ** 2 + mean_z ** 2)
            start_iso = timestamps[start_idx] if start_idx < len(timestamps) else ""
            end_iso = timestamps[end_idx - 1] if end_idx - 1 < len(timestamps) else ""
            results.append(
                {
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "activity_class": self._activity_classes[0],
                    "vector_magnitude": vm,
                }
            )
        return results
