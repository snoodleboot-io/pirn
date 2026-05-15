"""``AccelerometerActivityClassifier`` — classify physical activity from tri-axial accelerometer data.

Algorithm:
    1. Receive accel_data dict, sample_rate_hz, window_sec, and activity_classes.
    2. Validate accel_data is a dict, sample_rate_hz and window_sec are positive.
    3. Validate activity_classes is a non-empty tuple of strings.
    4. Segment the signal into windows of window_sec length at sample_rate_hz.
    5. Compute vector magnitude per window and assign the lowest activity class.

Math:
    Vector magnitude (VM) per window:

    $$\\text{VM} = \\sqrt{\\bar{x}^2 + \\bar{y}^2 + \\bar{z}^2}$$

    where $\\bar{x}$, $\\bar{y}$, $\\bar{z}$ are the per-window means of each axis.

References:
    - Troiano, R.P., et al. (2008). Physical activity in the United States measured by accelerometer.
    - Freedson, P.S., et al. (1998). Calibration of the Computer Science and Applications accelerometer.
"""

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
        accel_data: Knot | dict[str, Any],
        sample_rate_hz: Knot | float,
        window_sec: Knot | float,
        activity_classes: Knot | tuple[str, ...] = ("sedentary", "light", "moderate", "vigorous"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            accel_data=accel_data,
            sample_rate_hz=sample_rate_hz,
            window_sec=window_sec,
            activity_classes=activity_classes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        accel_data: dict[str, Any],
        sample_rate_hz: float,
        window_sec: float,
        activity_classes: tuple[str, ...] = ("sedentary", "light", "moderate", "vigorous"),
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Classify activity windows from tri-axial accelerometer readings.

        Args:
            accel_data: Dict with x (list of float), y (list of float),
                z (list of float), and timestamps_iso (list of str).
            sample_rate_hz: Sample rate in Hz (must be > 0).
            window_sec: Window length in seconds (must be > 0).
            activity_classes: Non-empty tuple of activity class label strings.

        Returns:
            List of dicts, each with start_iso, end_iso, activity_class,
            and vector_magnitude (float).

        Raises:
            TypeError: If accel_data is not a dict or activity_classes is not a tuple.
            ValueError: If sample_rate_hz or window_sec are not positive,
                or activity_classes is empty.
        """
        if not isinstance(accel_data, dict):
            raise TypeError("AccelerometerActivityClassifier: accel_data must be a dict")
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError("AccelerometerActivityClassifier: sample_rate_hz must be > 0")
        if not isinstance(window_sec, (int, float)) or window_sec <= 0:
            raise ValueError("AccelerometerActivityClassifier: window_sec must be > 0")
        if not isinstance(activity_classes, tuple) or len(activity_classes) == 0:
            raise ValueError(
                "AccelerometerActivityClassifier: activity_classes must be a non-empty tuple"
            )
        for field in ("x", "y", "z", "timestamps_iso"):
            if field not in accel_data:
                raise KeyError(
                    f"AccelerometerActivityClassifier: accel_data missing required field '{field}'; "
                    f"got: {list(accel_data)}"
                )
        accel_x = accel_data["x"]
        accel_y = accel_data["y"]
        accel_z = accel_data["z"]
        timestamps = accel_data["timestamps_iso"]
        window_samples = max(1, int(sample_rate_hz * window_sec))
        timestamp_count = len(timestamps)

        # First pass: compute per-window VM to establish the activity range.
        window_vms: list[float] = []
        for start_idx in range(0, timestamp_count, window_samples):
            end_idx = min(start_idx + window_samples, timestamp_count)
            window_x = accel_x[start_idx:end_idx]
            window_y = accel_y[start_idx:end_idx]
            window_z = accel_z[start_idx:end_idx]
            if window_x and window_y and window_z:
                mean_x = sum(window_x) / len(window_x)
                mean_y = sum(window_y) / len(window_y)
                mean_z = sum(window_z) / len(window_z)
                vm = math.sqrt(mean_x**2 + mean_y**2 + mean_z**2)
            else:
                vm = 0.0
            window_vms.append(vm)

        # ENMO-style: remove gravity (≈1 g) and clamp negative to zero.
        enmo_vals = [max(0.0, vm - 1.0) for vm in window_vms]
        enmo_max = max(enmo_vals) if enmo_vals else 0.0

        # Evenly-spaced thresholds across [0, enmo_max] for N classes.
        n_classes = len(activity_classes)
        step = enmo_max / n_classes if enmo_max > 0 else 1.0

        def _classify(enmo: float) -> str:
            idx = min(int(enmo / step), n_classes - 1) if step > 0 else 0
            return activity_classes[idx]

        results: list[dict[str, Any]] = []
        for window_index, (start_idx, vm) in enumerate(
            zip(range(0, timestamp_count, window_samples), window_vms, strict=False)
        ):
            end_idx = min(start_idx + window_samples, timestamp_count)
            start_iso = timestamps[start_idx] if start_idx < len(timestamps) else ""
            end_iso = timestamps[end_idx - 1] if end_idx - 1 < len(timestamps) else ""
            results.append(
                {
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "activity_class": _classify(enmo_vals[window_index]),
                    "vector_magnitude": vm,
                }
            )
        return results
