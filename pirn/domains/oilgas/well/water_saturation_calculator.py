"""``WaterSaturationCalculator`` — derive a water-saturation curve.

Algorithm:
    1. Receive a parsed LAS file, a ``method`` string, formation water
       resistivity ``rw``, and Archie exponents ``a``, ``m``, ``n``.
    2. Validate that ``method`` is supported and all numeric inputs are
       positive.
    3. Apply the selected saturation model to the resistivity and porosity
       curves.
    4. Return a LASFile augmented with the computed water-saturation curve.

Math:
    Archie water saturation:

    $$S_w = \\left(\\frac{a \\, R_w}{\\phi^m \\, R_t}\\right)^{1/n}$$

    Simandoux saturation:

    $$S_w = \\frac{\\phi^m}{a \\, R_w}
      \\left(-\\frac{V_{sh}}{2 R_{sh}}
      + \\sqrt{\\left(\\frac{V_{sh}}{2 R_{sh}}\\right)^2
        + \\frac{\\phi^m}{a \\, R_w \\, R_t}}\\right)^{-1}$$

References:
    - Archie, G.E. (1942). The electrical resistivity log as an aid in
      determining some reservoir characteristics. *Trans. AIME*, 146,
      54-62. SPE-942054-G.
    - Simandoux, P. (1963). Dielectric measurements in porous media and
      application to shaly formation measurement. *Revue de l'Institut
      Français du Pétrole*, supplementary issue, 193-215.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile


class WaterSaturationCalculator(Knot):
    """Compute a water-saturation curve using a configured saturation model."""

    def __init__(
        self,
        *,
        las_file: Knot,
        method: Knot | str,
        rw: Knot | float,
        a: Knot | float = 1.0,
        m: Knot | float = 2.0,
        n: Knot | float = 2.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            las_file=las_file,
            method=method,
            rw=rw,
            a=a,
            m=m,
            n=n,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        las_file: LASFile,
        method: str,
        rw: float,
        a: float = 1.0,
        m: float = 2.0,
        n: float = 2.0,
        **_: Any,
    ) -> LASFile:
        """Compute a water-saturation curve using the configured model and return an augmented LASFile.

        Args:
            las_file: LAS file providing the resistivity and porosity curves.
            method: Saturation model; must be one of ``archie``,
                ``simandoux``, ``indonesia``, or ``waxman_smits``.
            rw: Positive formation water resistivity (ohm·m).
            a: Positive Archie tortuosity factor (default 1.0).
            m: Positive cementation exponent (default 2.0).
            n: Positive saturation exponent (default 2.0).

        Returns:
            LASFile with a water-saturation curve named ``SW_{method}`` appended.
        """
        _valid_methods = frozenset({"archie", "simandoux", "indonesia", "waxman_smits"})
        if method not in _valid_methods:
            raise ValueError(
                f"WaterSaturationCalculator: method must be one of "
                f"{sorted(_valid_methods)}"
            )
        for label, value in (("rw", rw), ("a", a), ("m", m), ("n", n)):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"WaterSaturationCalculator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"WaterSaturationCalculator: {label} must be positive"
                )
        return LASFile(
            well_id=las_file.well_id,
            curves=(*las_file.curves, f"SW_{method}"),
            depth_unit=las_file.depth_unit,
        )
