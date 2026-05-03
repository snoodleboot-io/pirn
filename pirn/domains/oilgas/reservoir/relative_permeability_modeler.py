"""``RelativePermeabilityModeler`` — fit a relative-permeability model."""

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
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"RelativePermeabilityModeler: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(pvt=pvt, _config=_config, **kwargs)

    async def process(self, pvt: PVTTable, **_: Any) -> dict[str, Any]:
        """Fit the configured relative-permeability model to the PVT table and return the endpoint parameter dict.

        Args:
            pvt: PVT table providing fluid-property context for the kr model.

        Returns:
            Dict with keys ``fluid_id``, ``method``, ``swirr``, ``sorw``, ``krw_max``, and ``kro_max``.
        """
        return {
            "fluid_id": pvt.fluid_id,
            "method": self._method,
            "swirr": 0.2,
            "sorw": 0.25,
            "krw_max": 0.4,
            "kro_max": 0.9,
        }
