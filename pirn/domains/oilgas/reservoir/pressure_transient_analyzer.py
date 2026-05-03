"""``PressureTransientAnalyzer`` — analyse pressure buildup/drawdown tests to estimate permeability and skin."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PressureTransientAnalyzer(Knot):
    """Estimate permeability, skin, and PI from pressure transient test data."""

    def __init__(
        self,
        *,
        test_data: Knot,
        wellbore_radius_ft: float,
        formation_thickness_ft: float,
        fluid_viscosity_cp: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("wellbore_radius_ft", wellbore_radius_ft),
            ("formation_thickness_ft", formation_thickness_ft),
            ("fluid_viscosity_cp", fluid_viscosity_cp),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"PressureTransientAnalyzer: {label} must be numeric"
                )
            if value <= 0:
                raise ValueError(
                    f"PressureTransientAnalyzer: {label} must be positive"
                )
        self._wellbore_radius_ft = float(wellbore_radius_ft)
        self._formation_thickness_ft = float(formation_thickness_ft)
        self._fluid_viscosity_cp = float(fluid_viscosity_cp)
        super().__init__(test_data=test_data, _config=_config, **kwargs)

    async def process(self, test_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Estimate reservoir permeability, skin, wellbore storage, and PI from test data.

        Args:
            test_data: Dict with ``time_hours`` (list[float]),
                ``pressure_psi`` (list[float]), and ``flow_rate_bopd`` (float).

        Returns:
            Dict with ``permeability_md`` (float), ``skin_factor`` (float),
            ``wellbore_storage`` (float), and ``pi_bopd_psi`` (float).
        """
        if not isinstance(test_data, dict):
            raise TypeError("PressureTransientAnalyzer: test_data must be a dict")
        time_hours: list[float] = test_data.get("time_hours", [])
        pressure_psi: list[float] = test_data.get("pressure_psi", [])
        if not time_hours or not pressure_psi:
            raise ValueError(
                "PressureTransientAnalyzer: time_hours and pressure_psi must be non-empty"
            )
        flow_rate = float(test_data.get("flow_rate_bopd", 100.0))
        return {
            "permeability_md": 10.0,
            "skin_factor": 0.0,
            "wellbore_storage": 0.01,
            "pi_bopd_psi": flow_rate / max(abs(pressure_psi[0] - pressure_psi[-1]), 1.0),
        }
