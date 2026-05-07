"""``EspHealthMonitor`` — monitor electric submersible pump health indicators.

Algorithm:
    1. Receive ESP telemetry dict, ``vibration_threshold_g``, and
       ``temperature_threshold_c``.
    2. Validate that both thresholds are positive numbers.
    3. Compare motor temperature and vibration against thresholds.
    4. Penalise the health score for each threshold exceedance.
    5. Return health score, alert list, and recommended action.

Math:
    Health score starts at 100 and is decremented for each violated parameter:

    $$S_{\\text{health}} = 100 - 30 \\cdot \\mathbb{1}[T_{\\text{motor}} > T_{\\text{max}}]
      - 30 \\cdot \\mathbb{1}[a_{\\text{vib}} > a_{\\text{max}}]$$

    where :math:`\\mathbb{1}[\\cdot]` is the indicator function.

References:
    - API RP 11S4 (2002) — Recommended Practice for Sizing and Selection of
      Electric Submersible Pump Installations.
    - Takacs, G. (2009). *Electrical Submersible Pumps Manual*, 2nd ed.
      Gulf Professional Publishing, Chapter 6 (health monitoring).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EspHealthMonitor(Knot):
    """Evaluate ESP telemetry to produce a health score and actionable alerts."""

    def __init__(
        self,
        *,
        telemetry: Knot,
        vibration_threshold_g: Knot | float,
        temperature_threshold_c: Knot | float,
        temp_field: Knot | str = "motor_temp_c",
        vibration_field: Knot | str = "vibration_g",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            telemetry=telemetry,
            vibration_threshold_g=vibration_threshold_g,
            temperature_threshold_c=temperature_threshold_c,
            temp_field=temp_field,
            vibration_field=vibration_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        telemetry: dict[str, Any],
        vibration_threshold_g: float,
        temperature_threshold_c: float,
        temp_field: str = "motor_temp_c",
        vibration_field: str = "vibration_g",
        **_: Any,
    ) -> dict[str, Any]:
        """Evaluate ESP telemetry and return health score, alerts, and recommended action.

        Args:
            telemetry: Dict with motor temperature and vibration readings.
            vibration_threshold_g: Positive vibration alert threshold in g.
            temperature_threshold_c: Positive temperature alert threshold in °C.
            temp_field: Historian tag name for motor temperature (°C).
            vibration_field: Historian tag name for vibration level (g).

        Returns:
            Dict with ``health_score`` (float 0-100), ``alerts`` (list[str]),
            and ``recommended_action`` (str).

        Raises:
            KeyError: If telemetry is missing the temp_field or vibration_field key.
        """
        for label, value in (
            ("vibration_threshold_g", vibration_threshold_g),
            ("temperature_threshold_c", temperature_threshold_c),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"EspHealthMonitor: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"EspHealthMonitor: {label} must be positive")
        if not isinstance(telemetry, dict):
            raise TypeError("EspHealthMonitor: telemetry must be a dict")
        for field in (temp_field, vibration_field):
            if field not in telemetry:
                raise KeyError(
                    f"EspHealthMonitor: telemetry missing required field '{field}'; "
                    f"got: {list(telemetry)}"
                )
        alerts: list[str] = []
        score = 100.0
        motor_temp = float(telemetry[temp_field])
        vibration = float(telemetry[vibration_field])
        if motor_temp > temperature_threshold_c:
            alerts.append(f"{temp_field} {motor_temp:.1f} exceeds threshold")
            score -= 30.0
        if vibration > vibration_threshold_g:
            alerts.append(f"{vibration_field} {vibration:.2f} exceeds threshold")
            score -= 30.0
        recommended_action = "no_action" if not alerts else "inspect_esp"
        return {
            "health_score": max(0.0, score),
            "alerts": alerts,
            "recommended_action": recommended_action,
        }
