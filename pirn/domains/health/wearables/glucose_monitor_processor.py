"""``GlucoseMonitorProcessor`` — process CGM glucose-time-series rows.

Production version smooths the time series, derives standard CGM
metrics (TIR, MAGE, GMI), and emits per-day summaries. This stub
returns canonical CGM metric keys with zero values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GlucoseMonitorProcessor(Knot):
    """Process CGM rows into per-subject glucose metrics."""

    def __init__(
        self,
        *,
        readings: Sequence[Mapping[str, Any]],
        target_low_mg_dl: float,
        target_high_mg_dl: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(readings, (list, tuple)):
            raise TypeError(
                "GlucoseMonitorProcessor: readings must be list/tuple"
            )
        for reading in readings:
            if not isinstance(reading, Mapping):
                raise TypeError(
                    "GlucoseMonitorProcessor: every reading must be Mapping"
                )
        if not isinstance(target_low_mg_dl, (int, float)):
            raise TypeError(
                "GlucoseMonitorProcessor: target_low_mg_dl must be numeric"
            )
        if not isinstance(target_high_mg_dl, (int, float)):
            raise TypeError(
                "GlucoseMonitorProcessor: target_high_mg_dl must be numeric"
            )
        if float(target_low_mg_dl) >= float(target_high_mg_dl):
            raise ValueError(
                "GlucoseMonitorProcessor: target_low_mg_dl must be < target_high_mg_dl"
            )
        self._readings = tuple(dict(r) for r in readings)
        self._low = float(target_low_mg_dl)
        self._high = float(target_high_mg_dl)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        return {
            "mean_glucose": 0.0,
            "time_in_range_pct": 0.0,
            "time_below_range_pct": 0.0,
            "time_above_range_pct": 0.0,
            "gmi": 0.0,
            "cv": 0.0,
        }
