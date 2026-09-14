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


class EspHealthMonitor(Knot):
    """Evaluate ESP telemetry to produce a health score and actionable alerts."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def process(
        self,
        telemetry: dict[str, Any],
        vibration_threshold_g: float,
        temperature_threshold_c: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Evaluate ESP telemetry and return health score, alerts, and recommended action.

        Args:
            telemetry: Dict with ``motor_temp_c``, ``intake_pressure_psi``,
                ``vibration_g``, ``current_amps``, and ``voltage_v``.
            vibration_threshold_g: Positive vibration alert threshold in g.
            temperature_threshold_c: Positive temperature alert threshold in °C.

        Returns:
            Dict with ``health_score`` (float 0-100), ``alerts`` (list[str]),
            and ``recommended_action`` (str).
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
        alerts: list[str] = []
        score = 100.0
        if "motor_temp_c" not in telemetry:
            raise ValueError("EspHealthMonitor: required field 'motor_temp_c' missing from input")
        if "vibration_g" not in telemetry:
            raise ValueError("EspHealthMonitor: required field 'vibration_g' missing from input")
        motor_temp = float(telemetry["motor_temp_c"])
        vibration = float(telemetry["vibration_g"])
        if motor_temp > temperature_threshold_c:
            alerts.append(f"motor_temp_c {motor_temp:.1f} exceeds threshold")
            score -= 30.0
        if vibration > vibration_threshold_g:
            alerts.append(f"vibration_g {vibration:.2f} exceeds threshold")
            score -= 30.0
        recommended_action = "no_action" if not alerts else "inspect_esp"
        return {
            "health_score": max(0.0, score),
            "alerts": alerts,
            "recommended_action": recommended_action,
        }
