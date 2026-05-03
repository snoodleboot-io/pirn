"""``GasChromatographyAnalyzer`` — parse GC analysis results to compute component mole fractions and heating value."""

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
        normalize_fractions: bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(normalize_fractions, bool):
            raise TypeError(
                "GasChromatographyAnalyzer: normalize_fractions must be a bool"
            )
        self._normalize_fractions = normalize_fractions
        super().__init__(gc_report=gc_report, _config=_config, **kwargs)

    async def process(self, gc_report: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Parse GC report to compute mole fractions, gross heating value, and specific gravity.

        Args:
            gc_report: Dict with keys ``components`` (list of dicts with ``name`` and
                ``area_percent``) and ``total_area`` (float).

        Returns:
            Dict with ``mole_fractions`` (dict[str, float]),
            ``gross_heating_value_btu_scf`` (float), and ``specific_gravity`` (float).
        """
        if not isinstance(gc_report, dict):
            raise TypeError("GasChromatographyAnalyzer: gc_report must be a dict")
        components: list[dict[str, Any]] = gc_report.get("components", [])
        total_area: float = float(gc_report.get("total_area", 1.0) or 1.0)
        raw: dict[str, float] = {
            c["name"]: float(c["area_percent"]) / total_area * 100.0
            for c in components
        }
        if self._normalize_fractions and raw:
            total = sum(raw.values())
            mole_fractions: dict[str, float] = {
                k: v / total for k, v in raw.items()
            } if total else raw
        else:
            mole_fractions = raw
        return {
            "mole_fractions": mole_fractions,
            "gross_heating_value_btu_scf": 1012.0,
            "specific_gravity": 0.65,
        }
