"""``PermeabilityEstimator`` — estimate permeability from porosity / Sw curves.

Algorithm:
    1. Receive a LASPayload and a ``method`` string selecting the
       permeability correlation.
    2. Validate that ``method`` is one of ``timur``, ``coates``, or
       ``wyllie_rose``.
    3. Locate the porosity curve (first of PHI_density, PHI_neutron,
       PHI_density_neutron, NPHI) and the irreducible water saturation curve
       (first of SW_archie, SW_simandoux, SW_indonesia, SW_waxman_smits),
       defaulting Swi to 0.25 if no Sw curve is present.
    4. Apply the selected empirical correlation to compute a permeability curve.
    5. Return a LASPayload augmented with the computed permeability curve.

Math:
    Timur permeability correlation:

    $$k = \\frac{0.136 \\, \\phi^{4.4}}{S_{wirr}^2} \\quad [\\text{mD}]$$

    Coates permeability correlation:

    $$k = \\left(\\frac{\\phi^2}{C}\\right)^2
      \\left(\\frac{\\phi - S_{wirr}}{S_{wirr}}\\right)^2 \\quad [\\text{mD}]$$

References:
    - Timur, A. (1968). An investigation of permeability, porosity, and
      residual water saturation relationships for sandstone reservoirs.
      *The Log Analyst*, 9(4), 8-17.
    - Coates, G.R. & Dumanoir, J.L. (1974). A new approach to improved log-
      derived permeability. *The Log Analyst*, 15(1), 17-31.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload

_porosity_curve_priority = ("PHI_density", "PHI_neutron", "PHI_density_neutron", "NPHI")
_sw_curve_priority = ("SW_archie", "SW_simandoux", "SW_indonesia", "SW_waxman_smits")
_eps = 1e-9


def _find_porosity_curve(curve_data: dict[str, np.ndarray]) -> np.ndarray:
    for name in _porosity_curve_priority:
        if name in curve_data:
            return curve_data[name]
    raise ValueError(
        "PermeabilityEstimator: no porosity curve found in curve_data; run PorosityCalculator first"
    )


def _find_swi(curve_data: dict[str, np.ndarray], depth_count: int) -> np.ndarray:
    for name in _sw_curve_priority:
        if name in curve_data:
            return curve_data[name]
    return np.full(depth_count, 0.25, dtype=np.float64)


class PermeabilityEstimator(Knot):
    """Estimate a permeability curve using a configured correlation."""

    def __init__(
        self,
        *,
        payload: Knot,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, method=method, _config=_config, **kwargs)

    async def process(self, payload: LASPayload, method: str, **_: Any) -> LASPayload:
        """Compute a permeability curve from porosity and Sw inputs and return an augmented LASPayload.

        Args:
            payload: LASPayload providing the porosity and water-saturation curves.
            method: Permeability correlation; must be one of ``timur``,
                ``coates``, or ``wyllie_rose``.

        Returns:
            LASPayload with a permeability curve named ``K_{method}`` appended.
        """
        _valid_methods = frozenset({"timur", "coates", "wyllie_rose"})
        if method not in _valid_methods:
            raise ValueError(
                f"PermeabilityEstimator: method must be one of {sorted(_valid_methods)}"
            )

        curve_data = payload.curve_data
        phi = _find_porosity_curve(curve_data)
        swi = _find_swi(curve_data, len(phi))

        if method == "timur":
            permeability_curve = np.maximum(0.136 * phi**4.4 / (swi**2 + _eps), 0.0)
        elif method == "coates":
            coates_constant = 0.0314
            permeability_curve = np.maximum(
                (phi**2 / coates_constant) ** 2 * ((phi - swi) / (swi + _eps)) ** 2, 0.0
            )
        else:
            permeability_curve = np.maximum(250.0 * phi**3 / (swi + _eps) ** 2, 0.0)

        mnemonic = f"K_{method}"
        new_curve_data = {**curve_data, mnemonic: permeability_curve}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=(*payload.las.curves, mnemonic),
                depth_unit=payload.las.depth_unit,
            ),
            data=new_curve_data,
        )
