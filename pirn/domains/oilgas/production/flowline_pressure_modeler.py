"""``FlowlinePressureModeler`` — predict flowline pressure drop from rates.

Algorithm:
    1. Receive a flow-rate ScadaTimeSeries and pipe geometry parameters.
    2. Validate that all numeric parameters are positive.
    3. Apply the Darcy-Weisbach equation to compute pressure drop per unit length.
    4. Return a ScadaTimeSeries of pressure-drop values.

Math:
    Darcy-Weisbach pressure drop:

    $$\\Delta P = f \\frac{L}{D} \\frac{\\rho v^2}{2}$$

    where :math:`f` is the Darcy friction factor (Colebrook-White for
    turbulent flow), :math:`L` is pipe length (ft), :math:`D` is inner
    diameter (in), :math:`\\rho` is fluid density, and :math:`v` is flow
    velocity.

    Colebrook-White implicit equation:

    $$\\frac{1}{\\sqrt{f}} = -2 \\log_{10}\\!\\left(\\frac{\\varepsilon/D}{3.7} + \\frac{2.51}{Re\\sqrt{f}}\\right)$$

References:
    - Brill, J.P. & Mukherjee, H. (1999). *Multiphase Flow in Wells*. SPE
      Monograph Volume 17.
    - Darcy, H. (1857). *Recherches expérimentales relatives au mouvement de
      l'eau dans les tuyaux* (original Darcy-Weisbach derivation).
"""

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
        rate_series: Knot | ScadaTimeSeries,
        pipe_inner_diameter_in: Knot | float,
        pipe_length_ft: Knot | float,
        roughness_in: Knot | float = 0.0006,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rate_series=rate_series,
            pipe_inner_diameter_in=pipe_inner_diameter_in,
            pipe_length_ft=pipe_length_ft,
            roughness_in=roughness_in,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rate_series: ScadaTimeSeries,
        pipe_inner_diameter_in: float,
        pipe_length_ft: float,
        roughness_in: float = 0.0006,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Accept a flow-rate series and return a pressure-drop time series computed from the pipe geometry.

        Args:
            rate_series: ScadaTimeSeries of flow rates used as input to the
                pressure-drop model.
            pipe_inner_diameter_in: Positive pipe inner diameter in inches.
            pipe_length_ft: Positive pipe length in feet.
            roughness_in: Positive pipe roughness in inches (default 0.0006 in).

        Returns:
            ScadaTimeSeries of computed pressure-drop values with sensor_id
            prefixed ``dp:<rate_sensor_id>``.
        """
        for label, value in (
            ("pipe_inner_diameter_in", pipe_inner_diameter_in),
            ("pipe_length_ft", pipe_length_ft),
            ("roughness_in", roughness_in),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"FlowlinePressureModeler: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"FlowlinePressureModeler: {label} must be positive")
        return ScadaTimeSeries(
            sensor_id=f"dp:{rate_series.sensor_id}",
            sample_interval_sec=rate_series.sample_interval_sec,
        )
