"""``PorosityCalculator`` — derive a porosity curve from density / neutron logs.

Algorithm:
    1. Receive a LASPayload, a ``method`` string, a positive
       ``matrix_density``, and a positive ``fluid_density`` less than
       ``matrix_density``.
    2. Validate all inputs.
    3. Apply the selected porosity model (density, neutron, or
       density-neutron crossplot) to compute a porosity curve.
    4. Return a LASPayload augmented with the computed porosity curve.

Math:
    Density porosity:

    $$\\phi_D = \\frac{\\rho_{ma} - \\rho_b}{\\rho_{ma} - \\rho_{fl}}$$

    Density-neutron crossplot porosity:

    $$\\phi_{DN} = \\sqrt{\\frac{\\phi_D^2 + \\phi_N^2}{2}}$$

References:
    - Gaymard, R. & Poupon, A. (1968). Response of neutron and formation
      density logs in hydrocarbon bearing formations. *The Log Analyst*,
      9(5), 3-12.
    - Ellis, D.V. & Singer, J.M. (2007). *Well Logging for Earth Scientists*,
      2nd ed. Springer, Chapter 14 (porosity measurement).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload


def _compute_density(
    curve_data: dict[str, np.ndarray],
    matrix_density: float,
    fluid_density: float,
) -> np.ndarray:
    if "RHOB" not in curve_data:
        raise ValueError(
            "PorosityCalculator: 'RHOB' curve required in curve_data for density method"
        )
    rhob = curve_data["RHOB"]
    phi = (matrix_density - rhob) / (matrix_density - fluid_density)
    return np.clip(phi, 0.0, 1.0)


def _compute_neutron(curve_data: dict[str, np.ndarray]) -> np.ndarray:
    if "NPHI" not in curve_data:
        raise ValueError(
            "PorosityCalculator: 'NPHI' curve required in curve_data for neutron method"
        )
    return np.clip(curve_data["NPHI"], 0.0, 1.0)


def _compute_density_neutron(
    curve_data: dict[str, np.ndarray],
    matrix_density: float,
    fluid_density: float,
) -> np.ndarray:
    if "RHOB" not in curve_data:
        raise ValueError(
            "PorosityCalculator: 'RHOB' curve required in curve_data for density_neutron method"
        )
    if "NPHI" not in curve_data:
        raise ValueError(
            "PorosityCalculator: 'NPHI' curve required in curve_data for density_neutron method"
        )
    rhob = curve_data["RHOB"]
    phi_d = (matrix_density - rhob) / (matrix_density - fluid_density)
    phi_n = curve_data["NPHI"]
    phi_dn = np.sqrt((phi_d**2 + phi_n**2) / 2.0)
    return np.clip(phi_dn, 0.0, 1.0)


class PorosityCalculator(Knot):
    """Derive a porosity curve and append it to the LASPayload."""

    def __init__(
        self,
        *,
        payload: Knot,
        method: Knot | str,
        matrix_density: Knot | float,
        fluid_density: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            payload=payload,
            method=method,
            matrix_density=matrix_density,
            fluid_density=fluid_density,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        payload: LASPayload,
        method: str,
        matrix_density: float,
        fluid_density: float,
        **_: Any,
    ) -> LASPayload:
        """Derive a porosity curve from the payload curve data and return an augmented LASPayload.

        Args:
            payload: LASPayload providing the density and/or neutron log curves.
            method: Porosity model; must be one of ``density``, ``neutron``,
                or ``density_neutron``.
            matrix_density: Positive rock matrix density (g/cm³).
            fluid_density: Positive borehole fluid density (g/cm³); must be
                less than ``matrix_density``.

        Returns:
            LASPayload with a porosity curve named ``PHI_{method}`` appended.
        """
        _valid_methods = frozenset({"density", "neutron", "density_neutron"})
        if method not in _valid_methods:
            raise ValueError(f"PorosityCalculator: method must be one of {sorted(_valid_methods)}")
        for label, value in (
            ("matrix_density", matrix_density),
            ("fluid_density", fluid_density),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"PorosityCalculator: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"PorosityCalculator: {label} must be positive")
        if fluid_density >= matrix_density:
            raise ValueError("PorosityCalculator: fluid_density must be less than matrix_density")

        curve_data = payload.curve_data

        if method == "density":
            phi = await asyncio.to_thread(
                _compute_density, curve_data, matrix_density, fluid_density
            )
        elif method == "neutron":
            phi = await asyncio.to_thread(_compute_neutron, curve_data)
        else:
            phi = await asyncio.to_thread(
                _compute_density_neutron, curve_data, matrix_density, fluid_density
            )

        mnemonic = f"PHI_{method}"
        new_curve_data = {**curve_data, mnemonic: phi}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=(*payload.las.curves, mnemonic),
                depth_unit=payload.las.depth_unit,
            ),
            data=new_curve_data,
        )
