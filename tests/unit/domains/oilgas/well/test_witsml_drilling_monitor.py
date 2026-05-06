"""Unit tests for :class:`WitsmlDrillingMonitor`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.witsml_drilling_monitor import WitsmlDrillingMonitor
from pirn.tapestry import Tapestry


class _WitsmlSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "log_data": [
                {"depth_ft": 5000.0, "rop_ft_hr": 30.0, "wob_klbf": 20.0, "rpm": 120.0},
                {"depth_ft": 5001.0, "rop_ft_hr": 85.0, "wob_klbf": 25.0, "rpm": 130.0},
            ]
        }


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_well_uid(self) -> None:
        k = WitsmlDrillingMonitor.__new__(WitsmlDrillingMonitor)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "well_uid"):
            await k.process(
                witsml_data={"log_data": []},
                alert_thresholds={"rop_ft_hr": 80.0},
                well_uid="",
            )

    async def test_rejects_non_dict_thresholds(self) -> None:
        k = WitsmlDrillingMonitor.__new__(WitsmlDrillingMonitor)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(TypeError, "alert_thresholds"):
            await k.process(
                witsml_data={"log_data": []},
                alert_thresholds="not_a_dict",  # type: ignore[arg-type]
                well_uid="WELL-001",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_kpis_and_alerts(self) -> None:
        with Tapestry() as t:
            src = _WitsmlSource(_config=KnotConfig(id="src"))
            WitsmlDrillingMonitor(
                witsml_data=src,
                alert_thresholds={"rop_ft_hr": 80.0},
                well_uid="WELL-001",
                _config=KnotConfig(id="wdm"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wdm"]
        assert out["well_uid"] == "WELL-001"
        assert out["record_count"] == 2
        assert "rop_ft_hr" in out["kpis"]
        assert len(out["alerts"]) == 1  # second row exceeds 80 ft/hr

    async def test_no_alerts_below_threshold(self) -> None:
        class _NormalSource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> dict[str, Any]:
                return {
                    "log_data": [
                        {"depth_ft": 5000.0, "rop_ft_hr": 30.0},
                    ]
                }

        with Tapestry() as t:
            src = _NormalSource(_config=KnotConfig(id="src"))
            WitsmlDrillingMonitor(
                witsml_data=src,
                alert_thresholds={"rop_ft_hr": 80.0},
                well_uid="WELL-002",
                _config=KnotConfig(id="wdm"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wdm"]
        assert out["alerts"] == []
