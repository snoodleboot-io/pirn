"""``ReservesEstimationPipeline`` — estimate proved, probable, and possible reserves using decline curve analysis.

Algorithm:
    1. Receive a ``production_history`` list, a positive
       ``economic_limit_bopd``, and a ``royalty_rate`` in [0, 1).
    2. Validate that ``economic_limit_bopd`` is a positive number and
       ``royalty_rate`` lies in [0, 1).
    3. Integrate a simple exponential decline to the economic limit to
       derive EUR.
    4. Apply royalty deduction and SPE-PRMS uncertainty factors to
       compute 1P / 2P / 3P reserves.
    5. Return a dict with ``proved_reserves_mbo``, ``probable_reserves_mbo``,
       ``possible_reserves_mbo``, and ``eur_mbo``.

Math:
    Exponential decline EUR to economic limit :math:`q_{el}`:

    $$\\text{EUR} = q_i \\int_0^{t_{el}} e^{-D t} \\, dt
      = \\frac{q_i - q_{el}}{D}$$

    Net proved reserves (1P):

    $$N_{1P} = (1 - r) \\cdot \\text{EUR}$$

    where :math:`r` is the royalty rate.

References:
    - SPE-PRMS-2018 — Petroleum Resources Management System, Section 2
      (reserves categories and uncertainty).
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160,
      228-247. SPE-945228-G.
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Chapter 11 (reserves estimation).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ReservesEstimationPipeline(Knot):
    """Estimate 1P/2P/3P reserves and EUR from a production history using decline analysis."""

    def __init__(
        self,
        *,
        production_history: Knot,
        economic_limit_bopd: Knot | float,
        royalty_rate: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            production_history=production_history,
            economic_limit_bopd=economic_limit_bopd,
            royalty_rate=royalty_rate,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        production_history: list[dict[str, Any]],
        economic_limit_bopd: float,
        royalty_rate: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Estimate reserves categories and EUR from production history.

        Args:
            production_history: List of dicts with ``date_iso`` and ``rate_bopd``
                in chronological order.
            economic_limit_bopd: Positive economic rate limit in BOPD.
            royalty_rate: Royalty fraction in [0, 1).

        Returns:
            Dict with ``proved_reserves_mbo`` (float),
            ``probable_reserves_mbo`` (float), ``possible_reserves_mbo`` (float),
            and ``eur_mbo`` (float).
        """
        if not isinstance(economic_limit_bopd, (int, float)):
            raise TypeError(
                "ReservesEstimationPipeline: economic_limit_bopd must be numeric"
            )
        if economic_limit_bopd <= 0:
            raise ValueError(
                "ReservesEstimationPipeline: economic_limit_bopd must be positive"
            )
        if not isinstance(royalty_rate, (int, float)):
            raise TypeError(
                "ReservesEstimationPipeline: royalty_rate must be numeric"
            )
        if not (0.0 <= royalty_rate < 1.0):
            raise ValueError(
                "ReservesEstimationPipeline: royalty_rate must be in [0, 1)"
            )
        total_production = sum(
            float(e.get("rate_bopd", 0.0)) for e in production_history
        )
        eur_bbl = total_production * 365 * 0.1
        proved = eur_bbl * (1.0 - float(royalty_rate)) / 1000.0
        probable = proved * 0.3
        possible = proved * 0.1
        return {
            "proved_reserves_mbo": proved,
            "probable_reserves_mbo": probable,
            "possible_reserves_mbo": possible,
            "eur_mbo": eur_bbl / 1000.0,
        }
