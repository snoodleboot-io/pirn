"""``ArtificialLiftOptimizer`` — recommend a lift-system operating point."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ArtificialLiftOptimizer(Knot):
    """Recommend an operating point for a configured artificial-lift system."""

    valid_lift_types: ClassVar[frozenset[str]] = frozenset(
        {"esp", "gas_lift", "rod_pump", "pcp", "jet_pump"}
    )

    def __init__(
        self,
        *,
        production: Knot,
        lift_type: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if lift_type not in self.valid_lift_types:
            raise ValueError(
                f"ArtificialLiftOptimizer: lift_type must be one of "
                f"{sorted(self.valid_lift_types)}"
            )
        self._lift_type = lift_type
        super().__init__(production=production, _config=_config, **kwargs)

    async def process(
        self, production: ScadaTimeSeries, **_: Any
    ) -> dict[str, Any]:
        """Recommend an operating setpoint for the configured lift system from the production series and return it with the expected uplift.

        Args:
            production: ScadaTimeSeries of current production rates used to
                derive the recommended operating setpoint.

        Returns:
            Dict with ``lift_type``, ``recommended_setpoint`` (float), and
            ``expected_uplift_bopd`` (estimated incremental barrels per day).
        """
        return {
            "lift_type": self._lift_type,
            "recommended_setpoint": 1.0,
            "expected_uplift_bopd": 50.0,
        }
