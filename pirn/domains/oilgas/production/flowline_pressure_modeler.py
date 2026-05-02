"""``FlowlinePressureModeler`` — predict flowline pressure drop from rates."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class FlowlinePressureModeler(Knot):
    """Predict pressure drop along a flowline from rate and geometry inputs."""

    def __init__(
        self,
        *,
        rate_series: Knot,
        pipe_inner_diameter_in: float,
        pipe_length_ft: float,
        roughness_in: float = 0.0006,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("pipe_inner_diameter_in", pipe_inner_diameter_in),
            ("pipe_length_ft", pipe_length_ft),
            ("roughness_in", roughness_in),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"FlowlinePressureModeler: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"FlowlinePressureModeler: {label} must be positive"
                )
        self._pipe_inner_diameter_in = float(pipe_inner_diameter_in)
        self._pipe_length_ft = float(pipe_length_ft)
        self._roughness_in = float(roughness_in)
        super().__init__(rate_series=rate_series, _config=_config, **kwargs)

    async def process(
        self, rate_series: ScadaTimeSeries, **_: Any
    ) -> ScadaTimeSeries:
        return ScadaTimeSeries(
            sensor_id=f"dp:{rate_series.sensor_id}",
            sample_interval_sec=rate_series.sample_interval_sec,
        )
