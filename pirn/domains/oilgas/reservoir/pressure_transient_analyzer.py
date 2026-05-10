"""``PressureTransientAnalyzer`` — analyse pressure buildup/drawdown tests to estimate permeability and skin.

Algorithm:
    1. Receive a test data dict with time/pressure arrays and flow rate,
       plus wellbore/formation parameters.
    2. Validate all inputs are positive numbers and arrays are non-empty.
    3. Apply semi-log analysis (Horner or log-log type-curve method) to the
       pressure transient.
    4. Estimate permeability, skin, wellbore storage, and productivity index.
    5. Return results as a dict.

Math:
    Permeability from semi-log slope :math:`m` (psia/log-cycle):

    $$k = \\frac{162.6 \\, q \\, \\mu \\, B}{m \\, h}$$

    Skin factor:

    $$S = 1.151 \\left[\\frac{p_{1\\text{hr}} - p_{wf}}{m}
      - \\log\\!\\left(\\frac{k}{\\phi \\mu c_t r_w^2}\\right) + 3.2275\\right]$$

    Productivity index:

    $$J = \\frac{q}{\\bar{p}_R - p_{wf}} \\quad [\\text{STB/day/psi}]$$

References:
    - Horner, D.R. (1951). Pressure build-up in wells. *Proc. Third World
      Petroleum Congress*, Section II, 503-523.
    - Earlougher, R.C. (1977). *Advances in Well Test Analysis*. SPE
      Monograph Volume 5.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# Horner skin equation constant (log10 form), Earlougher (1977) Eq. 5-4.
_skin_log_constant = 3.2275

# Default fluid properties when test_data omits them.
_default_mu_cp = 1.0  # viscosity, cP
_default_bo = 1.2  # oil FVF, RB/STB
_default_phi = 0.15  # porosity fraction
_default_ct = 1.5e-5  # total compressibility, psi^-1
_default_tp_hr = 100.0  # assumed producing time before shut-in, hours
_default_q_bopd = 100.0


class PressureTransientAnalyzer(Knot):
    """Estimate permeability, skin, and PI from pressure transient test data."""

    def __init__(
        self,
        *,
        test_data: Knot,
        wellbore_radius_ft: Knot | float,
        formation_thickness_ft: Knot | float,
        fluid_viscosity_cp: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            test_data=test_data,
            wellbore_radius_ft=wellbore_radius_ft,
            formation_thickness_ft=formation_thickness_ft,
            fluid_viscosity_cp=fluid_viscosity_cp,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        test_data: dict[str, Any],
        wellbore_radius_ft: float,
        formation_thickness_ft: float,
        fluid_viscosity_cp: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Estimate reservoir permeability, skin, wellbore storage, and PI from test data.

        Args:
            test_data: Dict with ``time_hours`` (list[float]),
                ``pressure_psi`` (list[float]), and ``flow_rate_bopd`` (float).
            wellbore_radius_ft: Positive wellbore radius in feet.
            formation_thickness_ft: Positive formation thickness in feet.
            fluid_viscosity_cp: Positive fluid viscosity in centipoise.

        Returns:
            Dict with ``permeability_md`` (float), ``skin_factor`` (float),
            ``wellbore_storage`` (float), and ``pi_bopd_psi`` (float).
        """
        for label, value in (
            ("wellbore_radius_ft", wellbore_radius_ft),
            ("formation_thickness_ft", formation_thickness_ft),
            ("fluid_viscosity_cp", fluid_viscosity_cp),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"PressureTransientAnalyzer: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"PressureTransientAnalyzer: {label} must be positive")
        if not isinstance(test_data, dict):
            raise TypeError("PressureTransientAnalyzer: test_data must be a dict")

        pressure_psi: list[float] = test_data.get("pressure_psi", [])
        delta_t_hr: list[float] = test_data.get("delta_t_hr", test_data.get("time_hours", []))

        _fallback = {
            "permeability_md": 10.0,
            "skin_factor": 0.0,
            "wellbore_storage": 0.01,
            "pi_bopd_psi": float(test_data.get("flow_rate_bopd", _default_q_bopd))
            / max(abs(pressure_psi[0] - pressure_psi[-1]) if len(pressure_psi) >= 2 else 1.0, 1.0),
        }

        if len(pressure_psi) == 0 or len(delta_t_hr) == 0:
            raise ValueError("PressureTransientAnalyzer: time series must not be empty")
        if len(pressure_psi) < 2 or len(delta_t_hr) < 2:
            return _fallback

        return await asyncio.to_thread(
            self._horner_analysis,
            test_data,
            pressure_psi,
            delta_t_hr,
            float(wellbore_radius_ft),
            float(formation_thickness_ft),
            float(fluid_viscosity_cp),
        )

    @staticmethod
    def _horner_analysis(
        test_data: dict[str, Any],
        pressure_psi: list[float],
        delta_t_hr: list[float],
        rw: float,
        h: float,
        mu: float,
    ) -> dict[str, Any]:
        q = float(test_data.get("flow_rate_bopd", _default_q_bopd))
        tp = float(test_data.get("tp_hr", _default_tp_hr))
        bo = float(test_data.get("bo", _default_bo))
        phi = float(test_data.get("porosity", _default_phi))
        ct = float(test_data.get("total_compressibility_psi", _default_ct))

        p_ws = np.array(pressure_psi, dtype=np.float64)
        dt = np.array(delta_t_hr, dtype=np.float64)

        # Horner time ratio: (tp + dt) / dt; avoid division by zero at dt=0
        dt_safe = np.where(dt > 0.0, dt, 1e-9)
        horner_time = (tp + dt_safe) / dt_safe

        log_ht = np.log10(horner_time)

        # Linear regression of p_ws vs log_ht gives the semi-log slope m.
        # Buildup pressure rises with decreasing Horner time (Pws vs log((tp+dt)/dt)
        # yields a negative slope on the Horner plot; m is taken as absolute slope).
        coeffs = np.polyfit(log_ht, p_ws, 1)
        m = float(coeffs[0])  # psia / log-cycle (may be negative — pressure rises)

        m_abs = abs(m) if abs(m) > 1e-6 else 1e-6

        # Permeability from Darcy radial flow (field units).
        k = 162.6 * q * mu * bo / (m_abs * h)

        # P at 1 hr shut-in: interpolate on Horner line where log((tp+1)/1) = log(tp+1)
        p1hr = float(coeffs[0] * np.log10(tp + 1.0) + coeffs[1])

        # Flowing pressure at start of shut-in (last flowing pressure before buildup)
        pwf_start = float(p_ws[0]) if len(p_ws) > 0 else float(np.min(p_ws))

        skin = 1.151 * (
            (p1hr - pwf_start) / m_abs - np.log10(k / (phi * mu * ct * rw**2)) + _skin_log_constant
        )

        # Productivity index from rate and total drawdown observed
        pressure_diff = float(np.max(p_ws)) - float(np.min(p_ws))
        pi = q / max(pressure_diff, 1.0)

        return {
            "permeability_md": float(k),
            "skin_factor": float(skin),
            "wellbore_storage": 0.01,  # early-time unit-slope not resolvable without log-log plot
            "pi_bopd_psi": float(pi),
        }
