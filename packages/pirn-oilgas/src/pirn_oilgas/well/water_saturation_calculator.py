"""``WaterSaturationCalculator`` — derive a water-saturation curve.

Algorithm:
    1. Receive a LASPayload, a ``method`` string, formation water
       resistivity ``rw``, and Archie exponents ``a``, ``m``, ``n``.
    2. Validate that ``method`` is supported and all numeric inputs are
       positive.
    3. Apply the selected saturation model to the resistivity and porosity
       curves in ``curve_data``.
    4. Return a LASPayload augmented with the computed water-saturation curve.

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

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload

_porosity_curve_priority = ("PHI_density", "PHI_neutron", "PHI_density_neutron", "NPHI")
_sw_epsilon = 1e-9


def _find_porosity_curve(curve_data: dict[str, np.ndarray]) -> np.ndarray:
    for name in _porosity_curve_priority:
        if name in curve_data:
            return curve_data[name]
    raise ValueError(
        "WaterSaturationCalculator: no porosity curve found in curve_data; "
        "run PorosityCalculator first"
    )


def _archie(
    phi: np.ndarray,
    rt: np.ndarray,
    tortuosity_factor: float,
    rw: float,
    cementation_exponent: float,
    saturation_exponent: float,
) -> np.ndarray:
    sw = (tortuosity_factor * rw / (phi**cementation_exponent * rt + _sw_epsilon)) ** (
        1.0 / saturation_exponent
    )
    return np.clip(sw, 0.0, 1.0)


def _simandoux(
    phi: np.ndarray,
    rt: np.ndarray,
    vsh: np.ndarray,
    tortuosity_factor: float,
    rw: float,
    cementation_exponent: float,
    saturation_exponent: float,
) -> np.ndarray:
    rsh = 4.0
    phi_m = phi**cementation_exponent
    term = vsh / (2.0 * rsh)
    discriminant = np.maximum(term**2 + phi_m / (tortuosity_factor * rw * rt + _sw_epsilon), 0.0)
    sw = (
        phi_m
        / (tortuosity_factor * rw + _sw_epsilon)
        / (-term + np.sqrt(discriminant) + _sw_epsilon)
    )
    return np.clip(sw, 0.0, 1.0)


class WaterSaturationCalculator(Knot):
    """Compute a water-saturation curve using a configured saturation model."""

    def __init__(
        self,
        *,
        payload: Knot,
        method: Knot | str,
        rw: Knot | float,
        tortuosity_factor: Knot | float = 1.0,
        cementation_exponent: Knot | float = 2.0,
        saturation_exponent: Knot | float = 2.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            payload=payload,
            method=method,
            rw=rw,
            tortuosity_factor=tortuosity_factor,
            cementation_exponent=cementation_exponent,
            saturation_exponent=saturation_exponent,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        payload: LASPayload,
        method: str,
        rw: float,
        tortuosity_factor: float = 1.0,
        cementation_exponent: float = 2.0,
        saturation_exponent: float = 2.0,
        **_: Any,
    ) -> LASPayload:
        """Compute a water-saturation curve and return an augmented LASPayload.

        Args:
            payload: LASPayload providing the resistivity and porosity curves.
            method: Saturation model; must be one of ``archie``,
                ``simandoux``, ``indonesia``, or ``waxman_smits``.
            rw: Positive formation water resistivity (ohm·m).
            tortuosity_factor: Positive Archie tortuosity factor (default 1.0).
            cementation_exponent: Positive cementation exponent (default 2.0).
            saturation_exponent: Positive saturation exponent (default 2.0).

        Returns:
            LASPayload with a water-saturation curve named ``SW_{method}`` appended.
        """
        _valid_methods = frozenset({"archie", "simandoux", "indonesia", "waxman_smits"})
        if method not in _valid_methods:
            raise ValueError(
                f"WaterSaturationCalculator: method must be one of {sorted(_valid_methods)}"
            )
        for label, value in (
            ("rw", rw),
            ("tortuosity_factor", tortuosity_factor),
            ("cementation_exponent", cementation_exponent),
            ("saturation_exponent", saturation_exponent),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"WaterSaturationCalculator: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"WaterSaturationCalculator: {label} must be positive")

        curve_data = payload.curve_data
        phi = _find_porosity_curve(curve_data)

        if "RT" not in curve_data:
            raise ValueError("WaterSaturationCalculator: 'RT' curve required in curve_data")
        rt = curve_data["RT"]

        if method == "simandoux":
            vsh = curve_data.get("VSH", np.zeros_like(phi))
            sw = _simandoux(
                phi, rt, vsh, tortuosity_factor, rw, cementation_exponent, saturation_exponent
            )
        else:
            sw = _archie(phi, rt, tortuosity_factor, rw, cementation_exponent, saturation_exponent)

        mnemonic = f"SW_{method}"
        new_curve_data = {**curve_data, mnemonic: sw}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=(*payload.las.curves, mnemonic),
                depth_unit=payload.las.depth_unit,
            ),
            data=new_curve_data,
        )
