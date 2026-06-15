"""``PetrophysicalEvaluator`` — top-level petrophysics interpretation.

Algorithm:
    1. Receive a LASPayload containing raw log curves.
    2. Compute volume of shale (VSH) from the gamma-ray curve.
    3. Compute effective porosity (PHIE) from RHOB (preferred) or an existing
       PHI curve, corrected for clay volume.
    4. Compute water saturation (SW) via the Archie equation using RT if
       available, otherwise default to fully water-saturated (SW = 1.0).
    5. Return a LASPayload augmented with VSH, PHIE, and SW curves.

Math:
    Archie water saturation:

    $$S_w = \\left(\\frac{a \\, R_w}{\\phi^m \\, R_t}\\right)^{1/n}$$

    Volume of shale (linear gamma-ray index):

    $$V_{sh} = \\frac{GR - GR_{clean}}{GR_{shale} - GR_{clean}}$$

References:
    - Archie, G.E. (1942). The electrical resistivity log as an aid in
      determining some reservoir characteristics. *Trans. AIME*, 146,
      54-62. SPE-942054-G.
    - Dresser Industries (1979). *Log Interpretation Charts*. Dresser Atlas,
      Chapter 2 (porosity and fluid saturation).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload

_gr_clean = 20.0
_gr_shale = 120.0
_rho_ma = 2.65
_rho_fl = 1.0
_eps = 1e-9


def _compute_curves(
    curve_data: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if "GR" not in curve_data:
        raise ValueError("PetrophysicalEvaluator: need GR and either RHOB or a PHI curve")
    gr = curve_data["GR"]
    vsh = np.clip((gr - _gr_clean) / (_gr_shale - _gr_clean), 0.0, 1.0)

    if "RHOB" in curve_data:
        phi_d = np.clip((_rho_ma - curve_data["RHOB"]) / (_rho_ma - _rho_fl), 0.0, 1.0)
        phie = phi_d * (1.0 - vsh)
    else:
        phi_curve = next(
            (curve_data[k] for k in curve_data if k.startswith("PHI_")),
            None,
        )
        if phi_curve is None:
            raise ValueError("PetrophysicalEvaluator: need GR and either RHOB or a PHI curve")
        phie = phi_curve * (1.0 - vsh)

    depth_count = len(gr)
    if "RT" in curve_data:
        rt = curve_data["RT"]
        sw = np.clip((1.0 * 0.1 / (phie**2 * rt + _eps)) ** 0.5, 0.0, 1.0)
    else:
        sw = np.ones(depth_count, dtype=np.float64)

    return vsh, phie, sw


class PetrophysicalEvaluator(Knot):
    """Run a basic petrophysics interpretation pass over a normalised LASPayload.

    The result is itself a :class:`LASPayload` whose ``curves`` and
    ``curve_data`` are augmented with the standard interpreted-log mnemonics.
    """

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(self, payload: LASPayload, **_: Any) -> LASPayload:
        """Run a petrophysics interpretation pass and return a LASPayload augmented with VSH, PHIE, and SW curves.

        Args:
            payload: LASPayload to run the interpretation pass over; must contain
                a ``GR`` curve and either ``RHOB`` or a ``PHI_*`` curve.

        Returns:
            LASPayload with ``VSH``, ``PHIE``, and ``SW`` curves appended.
        """
        vsh, phie, sw = await asyncio.to_thread(_compute_curves, payload.curve_data)

        new_curve_data = {**payload.curve_data, "VSH": vsh, "PHIE": phie, "SW": sw}
        return LASPayload(
            metadata=LASFile(
                well_id=payload.las.well_id,
                curves=(*payload.las.curves, "VSH", "PHIE", "SW"),
                depth_unit=payload.las.depth_unit,
            ),
            data=new_curve_data,
        )
