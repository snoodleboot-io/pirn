"""``FlowlinePressureModeler`` — predict flowline pressure drop from rates.

Algorithm:
    1. Receive a flow-rate ScadaPayload and pipe geometry parameters.
    2. Validate that all numeric parameters are positive.
    3. Apply the Darcy-Weisbach equation to compute pressure drop per unit length.
    4. Return a ScadaPayload of pressure-drop values.

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

import asyncio
import math
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


def _darcy_weisbach(
    values: np.ndarray,
    pipe_inner_diameter_in: float,
    pipe_length_ft: float,
) -> np.ndarray:
    rho = 62.4
    D_ft = pipe_inner_diameter_in / 12.0
    A_ft2 = math.pi * (D_ft / 2) ** 2
    Q_ft3s = values * 5.615 / 86400
    velocity = Q_ft3s / (A_ft2 + 1e-12)
    Re = rho * velocity * D_ft / (1.0 * 6.72e-4)
    friction_factor = np.where(Re < 2300, 64 / (Re + 1e-9), 0.316 / (Re**0.25 + 1e-9))
    return friction_factor * (pipe_length_ft / D_ft) * (rho * velocity**2 / 2) / 144


class FlowlinePressureModeler(Knot):
    """Predict pressure drop along a flowline from rate and geometry inputs."""

    def __init__(
        self,
        *,
        rate_series: Knot | ScadaPayload,
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
        rate_series: ScadaPayload,
        pipe_inner_diameter_in: float,
        pipe_length_ft: float,
        roughness_in: float = 0.0006,
        **_: Any,
    ) -> ScadaPayload:
        """Accept a flow-rate payload and return a pressure-drop time series computed from the pipe geometry.

        Args:
            rate_series: ScadaPayload of flow rates used as input to the
                pressure-drop model.
            pipe_inner_diameter_in: Positive pipe inner diameter in inches.
            pipe_length_ft: Positive pipe length in feet.
            roughness_in: Positive pipe roughness in inches (default 0.0006 in).

        Returns:
            ScadaPayload of computed pressure-drop values with sensor_id
            prefixed ``dp:<rate_sensor_id>``.
        """
        if not isinstance(rate_series, ScadaPayload):
            raise TypeError("FlowlinePressureModeler: rate_series must be a ScadaPayload")
        for label, value in (
            ("pipe_inner_diameter_in", pipe_inner_diameter_in),
            ("pipe_length_ft", pipe_length_ft),
            ("roughness_in", roughness_in),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"FlowlinePressureModeler: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"FlowlinePressureModeler: {label} must be positive")
        dP_psi = await asyncio.to_thread(
            _darcy_weisbach,
            rate_series.values,
            pipe_inner_diameter_in,
            pipe_length_ft,
        )
        sample_count = len(dP_psi)
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=f"dp:{rate_series.series.sensor_id}",
                sample_count=sample_count,
                sample_interval_sec=rate_series.series.sample_interval_sec,
            ),
            data=dP_psi,
        )
