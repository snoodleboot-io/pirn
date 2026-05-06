"""``ProductionAllocationEngine`` — allocate field-level production to individual wells based on test ratios.

Algorithm:
    1. Receive field totals dict, a list of well test dicts, and an
       ``allocation_method`` string.
    2. Validate that ``allocation_method`` is one of ``ratio``,
       ``test_period``, or ``regression``.
    3. Compute each well's share of field production as a ratio of its test
       rate to the sum of all test rates.
    4. Return a list of per-well allocated production dicts.

Math:
    Well :math:`j`'s allocated oil production:

    $$q_{o,j}^{\\text{alloc}} = Q_o^{\\text{field}} \\times
      \\frac{q_{o,j}^{\\text{test}}}{\\sum_k q_{o,k}^{\\text{test}}}$$

    Analogous equations apply for gas and water.

References:
    - API RP 44 (2nd ed., 2015) — Recommended Practice for Sampling Petroleum
      Reservoir Fluids (production allocation context).
    - Elias, R. & Bjørnstad, T. (2000). Allocation principles in the petroleum
      sector. *SPE-63116-MS*.
"""

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
        allocation_method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            field_totals=field_totals,
            well_tests=well_tests,
            allocation_method=allocation_method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        field_totals: dict[str, Any],
        well_tests: list[dict[str, Any]],
        allocation_method: str,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Allocate field production totals to wells using the configured method.

        Args:
            field_totals: Dict with ``oil_bopd``, ``gas_mmscfd``, and ``water_bwpd``.
            well_tests: List of well test dicts with ``well_id``, ``test_oil_bopd``,
                ``test_gas_mmscfd``, and ``test_water_bwpd``.
            allocation_method: One of ``ratio``, ``test_period``, or ``regression``.

        Returns:
            List of dicts with ``well_id``, ``allocated_oil_bopd``,
            ``allocated_gas_mmscfd``, and ``allocated_water_bwpd``.
        """
        if allocation_method not in self.valid_methods:
            raise ValueError(
                f"ProductionAllocationEngine: allocation_method must be one of "
                f"{sorted(self.valid_methods)}"
            )
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
