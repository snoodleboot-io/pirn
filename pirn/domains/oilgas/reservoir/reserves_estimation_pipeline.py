"""``ReservesEstimationPipeline`` — estimate proved, probable, and possible reserves using decline curve analysis."""

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
        economic_limit_bopd: float,
        royalty_rate: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._economic_limit_bopd = float(economic_limit_bopd)
        self._royalty_rate = float(royalty_rate)
        super().__init__(
            production_history=production_history, _config=_config, **kwargs
        )

    async def process(
        self, production_history: list[dict[str, Any]], **_: Any
    ) -> dict[str, Any]:
        """Estimate reserves categories and EUR from production history.

        Args:
            production_history: List of dicts with ``date_iso`` and ``rate_bopd``
                in chronological order.

        Returns:
            Dict with ``proved_reserves_mbo`` (float),
            ``probable_reserves_mbo`` (float), ``possible_reserves_mbo`` (float),
            and ``eur_mbo`` (float).
        """
        total_production = sum(
            float(e.get("rate_bopd", 0.0)) for e in production_history
        )
        # Stub: integrate simple exponential decline to economic limit
        eur_bbl = total_production * 365 * 0.1
        proved = eur_bbl * (1.0 - self._royalty_rate) / 1000.0
        probable = proved * 0.3
        possible = proved * 0.1
        return {
            "proved_reserves_mbo": proved,
            "probable_reserves_mbo": probable,
            "possible_reserves_mbo": possible,
            "eur_mbo": eur_bbl / 1000.0,
        }
