"""``VolumetricEstimator`` — estimate hydrocarbon-in-place volumetrically."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VolumetricEstimator(Knot):
    """Compute OOIP or OGIP from area / thickness / porosity / Sw inputs."""

    def __init__(
        self,
        *,
        area_acres: float,
        net_thickness_ft: float,
        porosity_fraction: float,
        water_saturation_fraction: float,
        formation_volume_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("area_acres", area_acres),
            ("net_thickness_ft", net_thickness_ft),
            ("formation_volume_factor", formation_volume_factor),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"VolumetricEstimator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"VolumetricEstimator: {label} must be positive"
                )
        for label, value in (
            ("porosity_fraction", porosity_fraction),
            ("water_saturation_fraction", water_saturation_fraction),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"VolumetricEstimator: {label} must be numeric"
                )
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"VolumetricEstimator: {label} must lie in [0, 1]"
                )
        self._area_acres = float(area_acres)
        self._net_thickness_ft = float(net_thickness_ft)
        self._porosity_fraction = float(porosity_fraction)
        self._water_saturation_fraction = float(water_saturation_fraction)
        self._formation_volume_factor = float(formation_volume_factor)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> float:
        ooip_stb = (
            7758.0
            * self._area_acres
            * self._net_thickness_ft
            * self._porosity_fraction
            * (1.0 - self._water_saturation_fraction)
            / self._formation_volume_factor
        )
        return ooip_stb
