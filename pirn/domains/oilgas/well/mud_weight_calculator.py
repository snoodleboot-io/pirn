"""``MudWeightCalculator`` — recommend a mud-weight window for a depth interval.

Algorithm:
    1. Receive drilling parameters and three numeric inputs:
       ``pore_pressure_ppg``, ``fracture_pressure_ppg``, and an optional
       ``safety_margin_ppg`` (default 0.5).
    2. Validate all inputs are non-negative and that fracture pressure
       exceeds pore pressure.
    3. Compute the minimum mud weight as pore pressure plus the safety
       margin and the maximum as fracture pressure minus the margin.
    4. Return a dict with ``min_ppg`` and ``max_ppg``.

Math:
    Safe mud-weight window:

    $$MW_{min} = p_p + \\Delta_{safety}, \\quad
      MW_{max} = p_f - \\Delta_{safety}$$

    where :math:`p_p` is pore pressure, :math:`p_f` is fracture pressure,
    and :math:`\\Delta_{safety}` is the safety margin (all in ppg).

References:
    - Bourgoyne, A.T. et al. (1986). *Applied Drilling Engineering*. SPE
      Textbook Series Vol. 2, Chapter 6 (mud weight selection and drilling
      margins).
    - API RP 13C (2010) — Recommended Practice for Drill Stem Design and
      Operating Limits.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters


class MudWeightCalculator(Knot):
    """Recommend a mud-weight window from pore- and fracture-pressure inputs."""

    def __init__(
        self,
        *,
        drilling: Knot,
        pore_pressure_ppg: Knot | float,
        fracture_pressure_ppg: Knot | float,
        safety_margin_ppg: Knot | float = 0.5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            drilling=drilling,
            pore_pressure_ppg=pore_pressure_ppg,
            fracture_pressure_ppg=fracture_pressure_ppg,
            safety_margin_ppg=safety_margin_ppg,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        drilling: DrillingParameters,
        pore_pressure_ppg: float,
        fracture_pressure_ppg: float,
        safety_margin_ppg: float = 0.5,
        **_: Any,
    ) -> dict[str, float]:
        """Accept drilling parameters and return a min/max mud-weight window in ppg.

        Args:
            drilling: Drilling parameters providing wellbore context.
            pore_pressure_ppg: Non-negative pore pressure equivalent in ppg.
            fracture_pressure_ppg: Non-negative fracture pressure equivalent in ppg;
                must exceed ``pore_pressure_ppg``.
            safety_margin_ppg: Non-negative safety margin in ppg (default 0.5).

        Returns:
            Dict with keys ``min_ppg`` and ``max_ppg`` defining the safe mud-weight window.
        """
        for label, value in (
            ("pore_pressure_ppg", pore_pressure_ppg),
            ("fracture_pressure_ppg", fracture_pressure_ppg),
            ("safety_margin_ppg", safety_margin_ppg),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"MudWeightCalculator: {label} must be numeric")
            if value < 0.0:
                raise ValueError(f"MudWeightCalculator: {label} must be non-negative")
        if fracture_pressure_ppg <= pore_pressure_ppg:
            raise ValueError(
                "MudWeightCalculator: fracture_pressure_ppg must exceed pore_pressure_ppg"
            )
        return {
            "min_ppg": float(pore_pressure_ppg) + float(safety_margin_ppg),
            "max_ppg": float(fracture_pressure_ppg) - float(safety_margin_ppg),
        }
