"""``PorosityCalculator`` — derive a porosity curve from density / neutron logs.

Algorithm:
    1. Receive a parsed LAS file, a ``method`` string, a positive
       ``matrix_density``, and a positive ``fluid_density`` less than
       ``matrix_density``.
    2. Validate all inputs.
    3. Apply the selected porosity model (density, neutron, or
       density-neutron crossplot) to compute a porosity curve.
    4. Return a LASFile augmented with the computed porosity curve.

Math:
    Density porosity:

    $$\\phi_D = \\frac{\\rho_{ma} - \\rho_b}{\\rho_{ma} - \\rho_{fl}}$$

    Density-neutron crossplot porosity:

    $$\\phi_{DN} = \\sqrt{\\frac{\\phi_D^2 + \\phi_N^2}{2}}$$

References:
    - Gaymard, R. & Poupon, A. (1968). Response of neutron and formation
      density logs in hydrocarbon bearing formations. *The Log Analyst*,
      9(5), 3–12.
    - Ellis, D.V. & Singer, J.M. (2007). *Well Logging for Earth Scientists*,
      2nd ed. Springer, Chapter 14 (porosity measurement).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class PorosityCalculator(Knot):
    """Derive a porosity curve and append it to the LAS curve set."""

    def __init__(
        self,
        *,
        las_file: Knot,
        method: Knot | str,
        matrix_density: Knot | float,
        fluid_density: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            las_file=las_file,
            method=method,
            matrix_density=matrix_density,
            fluid_density=fluid_density,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        las_file: LASFile,
        method: str,
        matrix_density: float,
        fluid_density: float,
        **_: Any,
    ) -> LASFile:
        """Derive a porosity curve from the LAS log data and return an augmented LASFile.

        Args:
            las_file: LAS file providing the density and/or neutron log curves.
            method: Porosity model; must be one of ``density``, ``neutron``,
                or ``density_neutron``.
            matrix_density: Positive rock matrix density (g/cm³).
            fluid_density: Positive borehole fluid density (g/cm³); must be
                less than ``matrix_density``.

        Returns:
            LASFile with a porosity curve named ``PHI_{method}`` appended.
        """
        _valid_methods = frozenset({"density", "neutron", "density_neutron"})
        if method not in _valid_methods:
            raise ValueError(
                f"PorosityCalculator: method must be one of "
                f"{sorted(_valid_methods)}"
            )
        for label, value in (
            ("matrix_density", matrix_density),
            ("fluid_density", fluid_density),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"PorosityCalculator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"PorosityCalculator: {label} must be positive"
                )
        if fluid_density >= matrix_density:
            raise ValueError(
                "PorosityCalculator: fluid_density must be less than "
                "matrix_density"
            )
        return LASFile(
            well_id=las_file.well_id,
            curves=las_file.curves + (f"PHI_{method}",),
            depth_unit=las_file.depth_unit,
        )
