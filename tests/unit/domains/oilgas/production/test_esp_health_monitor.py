"""Unit tests for :class:`EspHealthMonitor`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.esp_health_monitor import EspHealthMonitor
from pirn.tapestry import Tapestry


class _TelemetrySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "motor_temp_c": 80.0,
            "intake_pressure_psi": 200.0,
            "vibration_g": 0.1,
            "current_amps": 50.0,
            "voltage_v": 480.0,
        }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_vibration_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "vibration_threshold_g"):
            with Tapestry():
                src = _TelemetrySource(_config=KnotConfig(id="src"))
                EspHealthMonitor(
                    telemetry=src,
                    vibration_threshold_g=0.0,
                    temperature_threshold_c=100.0,
                    _config=KnotConfig(id="esp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_healthy_esp(self) -> None:
        with Tapestry() as t:
            src = _TelemetrySource(_config=KnotConfig(id="src"))
            EspHealthMonitor(
                telemetry=src,
                vibration_threshold_g=1.0,
                temperature_threshold_c=100.0,
                _config=KnotConfig(id="esp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["esp"]
        assert out["health_score"] == 100.0
        assert out["alerts"] == []
        assert out["recommended_action"] == "no_action"

    async def test_alerts_on_high_temp(self) -> None:
        class _HotSource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> dict[str, Any]:
                return {"motor_temp_c": 150.0, "vibration_g": 0.1}

        with Tapestry() as t:
            src = _HotSource(_config=KnotConfig(id="src"))
            EspHealthMonitor(
                telemetry=src,
                vibration_threshold_g=1.0,
                temperature_threshold_c=100.0,
                _config=KnotConfig(id="esp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["esp"]
        assert len(out["alerts"]) > 0
        assert out["health_score"] < 100.0
