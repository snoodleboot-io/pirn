"""``ProductionAllocationEngine`` — allocate field-level production to individual wells based on test ratios."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ProductionAllocationEngine(Knot):
    """Allocate field totals to individual wells using well test ratios or regression."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"ratio", "test_period", "regression"}
    )

    def __init__(
        self,
        *,
        field_totals: Knot,
        well_tests: Knot,
        allocation_method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if allocation_method not in self.valid_methods:
            raise ValueError(
                f"ProductionAllocationEngine: allocation_method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._allocation_method = allocation_method
        super().__init__(
            field_totals=field_totals, well_tests=well_tests, _config=_config, **kwargs
        )

    async def process(
        self,
        field_totals: dict[str, Any],
        well_tests: list[dict[str, Any]],
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Allocate field production totals to wells using the configured method.

        Args:
            field_totals: Dict with ``oil_bopd``, ``gas_mmscfd``, and ``water_bwpd``.
            well_tests: List of well test dicts with ``well_id``, ``test_oil_bopd``,
                ``test_gas_mmscfd``, and ``test_water_bwpd``.

        Returns:
            List of dicts with ``well_id``, ``allocated_oil_bopd``,
            ``allocated_gas_mmscfd``, and ``allocated_water_bwpd``.
        """
        field_oil = float(field_totals.get("oil_bopd", 0.0))
        field_gas = float(field_totals.get("gas_mmscfd", 0.0))
        field_water = float(field_totals.get("water_bwpd", 0.0))
        total_test_oil = sum(float(w.get("test_oil_bopd", 0.0)) for w in well_tests) or 1.0
        total_test_gas = sum(float(w.get("test_gas_mmscfd", 0.0)) for w in well_tests) or 1.0
        total_test_water = sum(float(w.get("test_water_bwpd", 0.0)) for w in well_tests) or 1.0
        results: list[dict[str, Any]] = []
        for w in well_tests:
            results.append(
                {
                    "well_id": w["well_id"],
                    "allocated_oil_bopd": field_oil * float(w.get("test_oil_bopd", 0.0)) / total_test_oil,
                    "allocated_gas_mmscfd": field_gas * float(w.get("test_gas_mmscfd", 0.0)) / total_test_gas,
                    "allocated_water_bwpd": field_water * float(w.get("test_water_bwpd", 0.0)) / total_test_water,
                }
            )
        return results
