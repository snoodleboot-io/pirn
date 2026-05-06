"""Unit tests for :class:`EspHealthMonitor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.esp_health_monitor import EspHealthMonitor

_TELEMETRY: dict[str, Any] = {
    "motor_temp_c": 80.0,
    "intake_pressure_psi": 200.0,
    "vibration_g": 0.1,
    "current_amps": 50.0,
    "voltage_v": 480.0,
}
_HOT_TELEMETRY: dict[str, Any] = {"motor_temp_c": 150.0, "vibration_g": 0.1}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        vibration_threshold_g: float = 1.0,
        temperature_threshold_c: float = 100.0,
    ) -> EspHealthMonitor:
        return EspHealthMonitor(
            telemetry=None,  # type: ignore[arg-type]
            vibration_threshold_g=vibration_threshold_g,
            temperature_threshold_c=temperature_threshold_c,
            _config=KnotConfig(id="esp", validate_io=False),
        )

    async def test_rejects_non_positive_vibration_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "vibration_threshold_g"):
            await knot.process(
                telemetry=_TELEMETRY,
                vibration_threshold_g=0.0,
                temperature_threshold_c=100.0,
            )

    async def test_healthy_esp(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            telemetry=_TELEMETRY,
            vibration_threshold_g=1.0,
            temperature_threshold_c=100.0,
        )
        assert out["health_score"] == 100.0
        assert out["alerts"] == []
        assert out["recommended_action"] == "no_action"

    async def test_alerts_on_high_temp(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            telemetry=_HOT_TELEMETRY,
            vibration_threshold_g=1.0,
            temperature_threshold_c=100.0,
        )
        assert len(out["alerts"]) > 0
        assert out["health_score"] < 100.0
