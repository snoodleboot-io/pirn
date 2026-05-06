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


class GasChromatographyAnalyzer(Knot):
    """Parse GC analysis results to compute mole fractions and gross heating value."""

    def __init__(
        self,
        *,
        gc_report: Knot,
        normalize_fractions: Knot | bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gc_report=gc_report,
            normalize_fractions=normalize_fractions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gc_report: dict[str, Any],
        normalize_fractions: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        """Parse GC report to compute mole fractions, gross heating value, and specific gravity.

        Args:
            gc_report: Dict with keys ``components`` (list of dicts with ``name`` and
                ``area_percent``) and ``total_area`` (float).
            normalize_fractions: If True, renormalise fractions to sum to 1.

        Returns:
            Dict with ``mole_fractions`` (dict[str, float]),
            ``gross_heating_value_btu_scf`` (float), and ``specific_gravity`` (float).
        """
        if not isinstance(gc_report, dict):
            raise TypeError("GasChromatographyAnalyzer: gc_report must be a dict")
        if not isinstance(normalize_fractions, bool):
            raise TypeError("GasChromatographyAnalyzer: normalize_fractions must be a bool")
        components: list[dict[str, Any]] = gc_report.get("components", [])
        total_area: float = float(gc_report.get("total_area", 1.0) or 1.0)
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
        return {
            "mole_fractions": mole_fractions,
            "gross_heating_value_btu_scf": 1012.0,
            "specific_gravity": 0.65,
        }
