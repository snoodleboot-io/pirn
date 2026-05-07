"""``SeparatorTestProcessor`` — process separator test data to compute GOR, WOR, and shrinkage factors.

Algorithm:
    1. Receive a separator test data dict and ``separator_stages`` integer (1, 2, or 3).
    2. Validate that ``separator_stages`` is one of {1, 2, 3}.
    3. Extract oil rate, gas rate, and water rate from the test data.
    4. Compute GOR = gas_scfd / oil_bopd, WOR = water / oil.
    5. Compute oil shrinkage factor as a function of separator stage count.
    6. Return GOR, WOR, and oil shrinkage factor.

Math:
    Gas-oil ratio:

    $$\\text{GOR} = \\frac{q_g \\times 10^6}{q_o} \\quad [\\text{scf/bbl}]$$

    Water-oil ratio:

    $$\\text{WOR} = \\frac{q_w}{q_o}$$

    Oil shrinkage factor (empirical multi-stage separator approximation):

    $$B_o^{-1} \\approx \\frac{1}{1 + 0.05 \\cdot N_{\\text{stages}}}$$

References:
    - Standing, M.B. (1977). *Volumetric and Phase Behavior of Oil Field
      Hydrocarbon Systems*, 9th printing. SPE, Dallas.
    - API MPMS Chapter 12.2 — Calculation of Petroleum Quantities, Lease
      Automatic Custody Transfer (LACT) and Tank Gauging.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SeparatorTestProcessor(Knot):
    """Compute GOR, WOR, and oil shrinkage factor from separator test measurements."""

    def __init__(
        self,
        *,
        test_data: Knot,
        separator_stages: Knot | int,
        oil_rate_field: Knot | str = "oil_rate_bopd",
        gas_rate_field: Knot | str = "gas_rate_mmscfd",
        water_rate_field: Knot | str = "water_rate_bwpd",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            test_data=test_data,
            separator_stages=separator_stages,
            oil_rate_field=oil_rate_field,
            gas_rate_field=gas_rate_field,
            water_rate_field=water_rate_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        test_data: dict[str, Any],
        separator_stages: int,
        oil_rate_field: str = "oil_rate_bopd",
        gas_rate_field: str = "gas_rate_mmscfd",
        water_rate_field: str = "water_rate_bwpd",
        **_: Any,
    ) -> dict[str, Any]:
        """Compute GOR, WOR, and oil shrinkage from separator test data.

        Args:
            test_data: Dict with separator test rate measurements.
            separator_stages: Number of separator stages; must be 1, 2, or 3.
            oil_rate_field: Tag name for oil rate (bopd) in test_data.
            gas_rate_field: Tag name for gas rate (MMSCFD) in test_data.
            water_rate_field: Tag name for water rate (bwpd) in test_data.

        Returns:
            Dict with ``gor_scf_bbl`` (float), ``wor_bbl_bbl`` (float),
            and ``oil_shrinkage_factor`` (float).

        Raises:
            KeyError: If test_data is missing any required rate field.
        """
        if not isinstance(separator_stages, int):
            raise TypeError("SeparatorTestProcessor: separator_stages must be an int")
        if separator_stages not in {1, 2, 3}:
            raise ValueError("SeparatorTestProcessor: separator_stages must be 1, 2, or 3")
        if not isinstance(test_data, dict):
            raise TypeError("SeparatorTestProcessor: test_data must be a dict")
        for field in (oil_rate_field, gas_rate_field, water_rate_field):
            if field not in test_data:
                raise KeyError(
                    f"SeparatorTestProcessor: test_data missing required field '{field}'; "
                    f"got: {list(test_data)}"
                )
        oil = float(test_data[oil_rate_field]) or 1.0
        gas_mmscfd = float(test_data[gas_rate_field])
        water = float(test_data[water_rate_field])
        gas_scfd = gas_mmscfd * 1_000_000.0
        gor = gas_scfd / oil if oil else 0.0
        wor = water / oil if oil else 0.0
        shrinkage = 1.0 / (1.0 + 0.05 * separator_stages)
        return {
            "gor_scf_bbl": gor,
            "wor_bbl_bbl": wor,
            "oil_shrinkage_factor": shrinkage,
        }
