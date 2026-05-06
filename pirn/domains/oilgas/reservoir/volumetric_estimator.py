"""``VolumetricEstimator`` — estimate hydrocarbon-in-place volumetrically.

Algorithm:
    1. Receive area, net thickness, porosity, water saturation, and
       formation volume factor as inputs.
    2. Validate that all inputs are numeric; area, thickness, and FVF
       are positive; porosity and Sw lie in [0, 1].
    3. Apply the volumetric OOIP equation.
    4. Return OOIP in stock-tank barrels.

Math:
    Original oil in place (volumetric formula):

    $$N = \\frac{7758 \\, A \\, h \\, \\phi \\, (1 - S_w)}{B_{oi}}
      \\quad [\\text{STB}]$$

    where :math:`A` is area (acres), :math:`h` is net pay thickness (ft),
    :math:`\\phi` is porosity fraction, :math:`S_w` is water saturation
    fraction, and :math:`B_{oi}` is initial oil FVF (RB/STB).

References:
    - Craft, B.C. & Hawkins, M.F. (1991). *Applied Petroleum Reservoir
      Engineering*, 2nd ed. Prentice Hall, Chapter 1 (volumetric estimates).
    - Dake, L.P. (1983). *Fundamentals of Reservoir Engineering*. Elsevier,
      Chapter 1 (material volumes and FVF).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VolumetricEstimator(Knot):
    """Compute OOIP or OGIP from area / thickness / porosity / Sw inputs."""

    def __init__(
        self,
        *,
        area_acres: Knot | float,
        net_thickness_ft: Knot | float,
        porosity_fraction: Knot | float,
        water_saturation_fraction: Knot | float,
        formation_volume_factor: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            area_acres=area_acres,
            net_thickness_ft=net_thickness_ft,
            porosity_fraction=porosity_fraction,
            water_saturation_fraction=water_saturation_fraction,
            formation_volume_factor=formation_volume_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        area_acres: float,
        net_thickness_ft: float,
        porosity_fraction: float,
        water_saturation_fraction: float,
        formation_volume_factor: float,
        **_: Any,
    ) -> float:
        """Compute OOIP in stock-tank barrels from the configured area, thickness, porosity, Sw, and FVF inputs.

        Args:
            area_acres: Positive drainage area in acres.
            net_thickness_ft: Positive net pay thickness in feet.
            porosity_fraction: Porosity as a fraction in [0, 1].
            water_saturation_fraction: Water saturation as a fraction in [0, 1].
            formation_volume_factor: Positive initial oil FVF in RB/STB.

        Returns:
            OOIP in stock-tank barrels (float).
        """
        for label, value in (
            ("area_acres", area_acres),
            ("net_thickness_ft", net_thickness_ft),
            ("formation_volume_factor", formation_volume_factor),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"VolumetricEstimator: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"VolumetricEstimator: {label} must be positive")
        for label, value in (
            ("porosity_fraction", porosity_fraction),
            ("water_saturation_fraction", water_saturation_fraction),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"VolumetricEstimator: {label} must be numeric")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"VolumetricEstimator: {label} must lie in [0, 1]")
        return (
            7758.0
            * float(area_acres)
            * float(net_thickness_ft)
            * float(porosity_fraction)
            * (1.0 - float(water_saturation_fraction))
            / float(formation_volume_factor)
        )
