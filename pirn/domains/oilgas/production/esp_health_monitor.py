"""``EspHealthMonitor`` — monitor electric submersible pump health indicators."""

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
        vibration_threshold_g: float,
        temperature_threshold_c: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("vibration_threshold_g", vibration_threshold_g),
            ("temperature_threshold_c", temperature_threshold_c),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"EspHealthMonitor: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"EspHealthMonitor: {label} must be positive")
        self._vibration_threshold_g = float(vibration_threshold_g)
        self._temperature_threshold_c = float(temperature_threshold_c)
        super().__init__(telemetry=telemetry, _config=_config, **kwargs)

    async def process(self, telemetry: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Evaluate ESP telemetry and return health score, alerts, and recommended action.

        Args:
            telemetry: Dict with ``motor_temp_c``, ``intake_pressure_psi``,
                ``vibration_g``, ``current_amps``, and ``voltage_v``.

        Returns:
            Dict with ``health_score`` (float 0–100), ``alerts`` (list[str]),
            and ``recommended_action`` (str).
        """
        if not isinstance(telemetry, dict):
            raise TypeError("EspHealthMonitor: telemetry must be a dict")
        alerts: list[str] = []
        score = 100.0
        motor_temp = float(telemetry.get("motor_temp_c", 0.0))
        vibration = float(telemetry.get("vibration_g", 0.0))
        if motor_temp > self._temperature_threshold_c:
            alerts.append(f"motor_temp_c {motor_temp:.1f} exceeds threshold")
            score -= 30.0
        if vibration > self._vibration_threshold_g:
            alerts.append(f"vibration_g {vibration:.2f} exceeds threshold")
            score -= 30.0
        recommended_action = "no_action" if not alerts else "inspect_esp"
        return {
            "health_score": max(0.0, score),
            "alerts": alerts,
            "recommended_action": recommended_action,
        }
