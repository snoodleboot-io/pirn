"""``WitsmlDrillingMonitor`` — parse WITSML drilling data and monitor real-time drilling KPIs."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WitsmlDrillingMonitor(Knot):
    """Parse WITSML log data and evaluate drilling KPIs against alert thresholds."""

    def __init__(
        self,
        *,
        witsml_data: Knot,
        alert_thresholds: dict[str, float],
        well_uid: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(well_uid, str) or not well_uid:
            raise ValueError(
                "WitsmlDrillingMonitor: well_uid must be a non-empty string"
            )
        if not isinstance(alert_thresholds, dict):
            raise TypeError(
                "WitsmlDrillingMonitor: alert_thresholds must be a dict"
            )
        self._well_uid = well_uid
        self._alert_thresholds = alert_thresholds
        super().__init__(witsml_data=witsml_data, _config=_config, **kwargs)

    async def process(self, witsml_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Parse WITSML log and return KPIs and threshold alerts.

        Args:
            witsml_data: Dict with ``log_data`` (list of dicts with drilling
                parameters such as ``depth_ft``, ``rop_ft_hr``, ``wob_klbf``,
                ``rpm``).

        Returns:
            Dict with ``well_uid`` (str), ``record_count`` (int),
            ``kpis`` (dict), and ``alerts`` (list[str]).
        """
        if not isinstance(witsml_data, dict):
            raise TypeError("WitsmlDrillingMonitor: witsml_data must be a dict")
        log_data: list[dict[str, Any]] = witsml_data.get("log_data", [])
        alerts: list[str] = []
        kpi_totals: dict[str, float] = {}
        for row in log_data:
            for param, threshold in self._alert_thresholds.items():
                value = float(row.get(param, 0.0))
                kpi_totals[param] = kpi_totals.get(param, 0.0) + value
                if value > threshold:
                    alert_msg = f"{param} {value:.2f} exceeds threshold {threshold}"
                    if alert_msg not in alerts:
                        alerts.append(alert_msg)
        count = len(log_data)
        kpis = {
            k: v / count if count else 0.0 for k, v in kpi_totals.items()
        }
        return {
            "well_uid": self._well_uid,
            "record_count": count,
            "kpis": kpis,
            "alerts": alerts,
        }
