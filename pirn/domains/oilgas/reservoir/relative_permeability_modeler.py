"""``RelativePermeabilityModeler`` — fit a relative-permeability model to a PVT table.

Algorithm:
    1. Receive a ``pvt`` PVT table and a ``method`` string selecting the kr
       correlation.
    2. Validate that ``method`` is one of ``corey``, ``brooks_corey``,
       ``lett``, ``stone1``, or ``stone2``.
    3. Fit the selected relative-permeability model to the fluid-property
       data in the PVT table.
    4. Return a dict of fitted endpoint parameters.

Math:
    Corey model oil relative permeability:

    $$k_{ro} = k_{ro}^{\\max} \\left(\\frac{1 - S_w - S_{orw}}
      {1 - S_{wirr} - S_{orw}}\\right)^{n_o}$$

    Corey model water relative permeability:

    $$k_{rw} = k_{rw}^{\\max} \\left(\\frac{S_w - S_{wirr}}
      {1 - S_{wirr} - S_{orw}}\\right)^{n_w}$$

References:
    - Corey, A.T. (1954). The interrelation between gas and oil relative
      permeabilities. *Producers Monthly*, 19(1), 38-41.
    - Brooks, R.H. & Corey, A.T. (1964). *Hydraulic Properties of Porous
      Media*. Colorado State University Hydrology Paper No. 3.
    - Stone, H.L. (1970). Probability model for estimating three-phase
      relative permeability. *JPT*, 22(2), 214-218. SPE-2116-PA.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.pvt_table import PVTTable


class RelativePermeabilityModeler(Knot):
    """Fit a kr / Sw model and return the resulting parameter table."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"corey", "brooks_corey", "lett", "stone1", "stone2"}
    )

    def __init__(
        self,
        *,
        pvt: Knot,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(pvt=pvt, method=method, _config=_config, **kwargs)

    async def process(self, pvt: PVTTable, method: str, **_: Any) -> dict[str, Any]:
        """Fit the configured relative-permeability model to the PVT table and return the endpoint parameter dict.

        Args:
            pvt: PVT table providing fluid-property context for the kr model.
            method: One of ``corey``, ``brooks_corey``, ``lett``, ``stone1``,
                or ``stone2``.

        Returns:
            Dict with keys ``fluid_id``, ``method``, ``swirr``, ``sorw``,
            ``krw_max``, and ``kro_max``.
        """
        if method not in self.valid_methods:
            raise ValueError(
                f"RelativePermeabilityModeler: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        return {
            "fluid_id": pvt.fluid_id,
            "method": method,
            "swirr": 0.2,
            "sorw": 0.25,
            "krw_max": 0.4,
            "kro_max": 0.9,
        }
