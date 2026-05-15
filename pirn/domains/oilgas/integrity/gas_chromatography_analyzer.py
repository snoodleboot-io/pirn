"""``GasChromatographyAnalyzer`` — parse GC analysis results to compute component mole fractions and heating value.

Algorithm:
    1. Receive a ``gc_report`` dict and a ``normalize_fractions`` bool.
    2. Validate that ``gc_report`` is a dict and ``normalize_fractions`` is a bool.
    3. Extract component area percentages and convert to raw mole fractions by
       normalising against total area.
    4. If ``normalize_fractions`` is True, renormalise so all fractions sum to 1.
    5. Return mole fractions, gross heating value, and specific gravity.

Math:
    Raw mole fraction for component :math:`i`:

    $$x_i^{\\text{raw}} = \\frac{A_i}{A_{\\text{total}}} \\times 100$$

    Normalised fraction:

    $$x_i = \\frac{x_i^{\\text{raw}}}{\\sum_j x_j^{\\text{raw}}}$$

    Gross heating value is approximated from the component mole fractions
    using ideal-gas calorific values (GPA 2145, Table 1).

References:
    - GPA Midstream 2145-16 — Table of Physical Properties for Hydrocarbons and
      Other Compounds of Interest to the Natural Gas Industry.
    - ASTM D1945-14 — Standard Method for Analysis of Natural Gas by Gas
       Chromatography.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# GPA 2145-16, Table 1: gross (higher) heating value in BTU/scf at 60°F, 14.696 psia.
_hhv_btu_scf: dict[str, float] = {
    "CH4": 1012.0,
    "C2H6": 1769.0,
    "C3H8": 2516.0,
    "iC4": 3252.0,
    "nC4": 3262.0,
    "iC5": 4000.0,
    "nC5": 4009.0,
    "C6": 4755.0,
    "N2": 0.0,
    "CO2": 0.0,
    "H2S": 637.0,
}

# GPA 2145-16, Table 1: molecular weights (g/mol).
_mw: dict[str, float] = {
    "CH4": 16.04,
    "C2H6": 30.07,
    "C3H8": 44.10,
    "iC4": 58.12,
    "nC4": 58.12,
    "iC5": 72.15,
    "nC5": 72.15,
    "C6": 86.18,
    "N2": 28.01,
    "CO2": 44.01,
    "H2S": 34.08,
}

# Molecular weight of dry air (used as denominator for specific gravity).
_mw_air = 28.97


class GasChromatographyAnalyzer(Knot):
    """Parse GC analysis results to compute mole fractions and gross heating value."""

    def __init__(
        self,
        *,
        gc_report: Knot,
        normalize_fractions: Knot | bool = True,
        components_field: Knot | str = "components",
        total_area_field: Knot | str = "total_area",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gc_report=gc_report,
            normalize_fractions=normalize_fractions,
            components_field=components_field,
            total_area_field=total_area_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gc_report: dict[str, Any],
        normalize_fractions: bool = True,
        components_field: str = "components",
        total_area_field: str = "total_area",
        **_: Any,
    ) -> dict[str, Any]:
        """Parse GC report to compute mole fractions, gross heating value, and specific gravity.

        Args:
            gc_report: Dict containing component area data from the chromatograph.
            normalize_fractions: If True, renormalise fractions to sum to 1.
            components_field: Key for the components list in gc_report.
            total_area_field: Key for the total peak area in gc_report.

        Returns:
            Dict with ``mole_fractions`` (dict[str, float]),
            ``gross_heating_value_btu_scf`` (float), and ``specific_gravity`` (float).

        Raises:
            KeyError: If gc_report is missing the components_field or total_area_field key.
        """
        if not isinstance(gc_report, dict):
            raise TypeError("GasChromatographyAnalyzer: gc_report must be a dict")
        if not isinstance(normalize_fractions, bool):
            raise TypeError("GasChromatographyAnalyzer: normalize_fractions must be a bool")
        for field in (components_field, total_area_field):
            if field not in gc_report:
                raise KeyError(
                    f"GasChromatographyAnalyzer: gc_report missing required field '{field}'; "
                    f"got: {list(gc_report)}"
                )
        components: list[dict[str, Any]] = gc_report[components_field]
        total_area: float = float(gc_report[total_area_field]) or 1.0
        raw: dict[str, float] = {
            c["name"]: float(c["area_percent"]) / total_area * 100.0 for c in components
        }
        if normalize_fractions and raw:
            total = sum(raw.values())
            mole_fractions: dict[str, float] = (
                {k: v / total for k, v in raw.items()} if total else raw
            )
        else:
            mole_fractions = raw

        # GHV: sum of (mole fraction x component HHV) using GPA 2145-16 values.
        ghv = sum(yi * _hhv_btu_scf.get(name, 0.0) for name, yi in mole_fractions.items())

        # Specific gravity: mixture MW / air MW (Kay's mixing rule for ideal gas).
        sg = sum(yi * _mw.get(name, 0.0) for name, yi in mole_fractions.items()) / _mw_air

        return {
            "mole_fractions": mole_fractions,
            "gross_heating_value_btu_scf": float(ghv),
            "specific_gravity": float(sg),
        }
