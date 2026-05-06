"""``WitsmlDrillingMonitor`` — parse WITSML drilling data and monitor real-time drilling KPIs.

Algorithm:
    1. Receive a WITSML log data dict, an ``alert_thresholds`` dict of
       parameter-to-threshold mappings, and a non-empty ``well_uid`` string.
    2. Validate that the input is a dict and ``well_uid`` is non-empty.
    3. Iterate over log rows and accumulate KPI totals; emit an alert string
       for each row where a parameter exceeds its threshold.
    4. Return a dict with KPI averages, alert list, and record count.

Math:
    Average KPI for parameter :math:`k`:

    $$\\overline{KPI}_k = \\frac{1}{N} \\sum_{i=1}^{N} v_{k,i}$$

References:
    - Energistics (2019). *WITSML Data Exchange Standard*, Version 2.0
      (log object structure and channel data).
    - API RP 7G (2002) — Recommended Practice for Drill Stem Design and
      Operating Limits.
"""

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
        alert_thresholds: Knot | dict[str, float],
        well_uid: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            witsml_data=witsml_data,
            alert_thresholds=alert_thresholds,
            well_uid=well_uid,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        witsml_data: dict[str, Any],
        alert_thresholds: dict[str, float],
        well_uid: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Parse WITSML log and return KPIs and threshold alerts.

        Args:
            witsml_data: Dict with ``log_data`` (list of dicts with drilling
                parameters such as ``depth_ft``, ``rop_ft_hr``, ``wob_klbf``,
                ``rpm``).
            alert_thresholds: Dict mapping parameter names to their alert
                threshold values.
            well_uid: Non-empty WITSML well UID string.

        Returns:
            Dict with ``well_uid`` (str), ``record_count`` (int),
            ``kpis`` (dict), and ``alerts`` (list[str]).
        """
        if not isinstance(well_uid, str) or not well_uid:
            raise ValueError("WitsmlDrillingMonitor: well_uid must be a non-empty string")
        if not isinstance(alert_thresholds, dict):
            raise TypeError("WitsmlDrillingMonitor: alert_thresholds must be a dict")
        if not isinstance(witsml_data, dict):
            raise TypeError("WitsmlDrillingMonitor: witsml_data must be a dict")
        log_data: list[dict[str, Any]] = witsml_data.get("log_data", [])
        alerts: list[str] = []
        kpi_totals: dict[str, float] = {}
        for row in log_data:
            for param, threshold in alert_thresholds.items():
                value = float(row.get(param, 0.0))
                kpi_totals[param] = kpi_totals.get(param, 0.0) + value
                if value > threshold:
                    alert_msg = f"{param} {value:.2f} exceeds threshold {threshold}"
                    if alert_msg not in alerts:
                        alerts.append(alert_msg)
        count = len(log_data)
        kpis = {k: v / count if count else 0.0 for k, v in kpi_totals.items()}
        return {
            "well_uid": well_uid,
            "record_count": count,
            "kpis": kpis,
            "alerts": alerts,
        }
