"""``SeparatorTestProcessor`` — process separator test data to compute GOR, WOR, and shrinkage factors."""

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
        separator_stages: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(separator_stages, int):
            raise TypeError("SeparatorTestProcessor: separator_stages must be an int")
        if separator_stages not in {1, 2, 3}:
            raise ValueError(
                "SeparatorTestProcessor: separator_stages must be 1, 2, or 3"
            )
        self._separator_stages = separator_stages
        super().__init__(test_data=test_data, _config=_config, **kwargs)

    async def process(self, test_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Compute GOR, WOR, and oil shrinkage from separator test data.

        Args:
            test_data: Dict with ``oil_rate_bopd``, ``gas_rate_mmscfd``,
                ``water_rate_bwpd``, ``separator_pressure_psig``,
                and ``separator_temp_f``.

        Returns:
            Dict with ``gor_scf_bbl`` (float), ``wor_bbl_bbl`` (float),
            and ``oil_shrinkage_factor`` (float).
        """
        if not isinstance(test_data, dict):
            raise TypeError("SeparatorTestProcessor: test_data must be a dict")
        oil = float(test_data.get("oil_rate_bopd", 1.0) or 1.0)
        gas_mmscfd = float(test_data.get("gas_rate_mmscfd", 0.0))
        water = float(test_data.get("water_rate_bwpd", 0.0))
        gas_scfd = gas_mmscfd * 1_000_000.0
        gor = gas_scfd / oil if oil else 0.0
        wor = water / oil if oil else 0.0
        shrinkage = 1.0 / (1.0 + 0.05 * self._separator_stages)
        return {
            "gor_scf_bbl": gor,
            "wor_bbl_bbl": wor,
            "oil_shrinkage_factor": shrinkage,
        }
