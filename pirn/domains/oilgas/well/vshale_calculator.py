"""``VshaleCalculator`` — compute volume of shale from gamma ray log."""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VshaleCalculator(Knot):
    """Compute Vshale from a gamma ray log using linear or non-linear transforms."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"linear", "larionov_older", "larionov_tertiary", "clavier"}
    )

    def __init__(
        self,
        *,
        gr_log: Knot,
        gr_clean: float,
        gr_shale: float,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (("gr_clean", gr_clean), ("gr_shale", gr_shale)):
            if not isinstance(value, (int, float)):
                raise TypeError(f"VshaleCalculator: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"VshaleCalculator: {label} must be positive")
        if gr_shale <= gr_clean:
            raise ValueError(
                "VshaleCalculator: gr_shale must be greater than gr_clean"
            )
        if method not in self.valid_methods:
            raise ValueError(
                f"VshaleCalculator: method must be one of {sorted(self.valid_methods)}"
            )
        self._gr_clean = float(gr_clean)
        self._gr_shale = float(gr_shale)
        self._method = method
        super().__init__(gr_log=gr_log, _config=_config, **kwargs)

    def _igr(self, gr_api: float) -> float:
        denom = self._gr_shale - self._gr_clean
        return max(0.0, min(1.0, (gr_api - self._gr_clean) / denom)) if denom else 0.0

    def _vshale(self, igr: float) -> float:
        if self._method == "linear":
            return igr
        if self._method == "larionov_older":
            return 0.33 * (2.0 ** (2.0 * igr) - 1.0)
        if self._method == "larionov_tertiary":
            return 0.083 * (2.0 ** (3.7 * igr) - 1.0)
        # clavier
        return 1.7 - math.sqrt(3.38 - (igr + 0.7) ** 2)

    async def process(
        self, gr_log: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Compute Vshale for each log sample using the configured transform.

        Args:
            gr_log: List of dicts with ``depth_ft`` and ``gr_api``.

        Returns:
            List of dicts with ``depth_ft``, ``gr_api``, and ``vshale``.
        """
        results: list[dict[str, Any]] = []
        for entry in gr_log:
            gr = float(entry.get("gr_api", 0.0))
            igr = self._igr(gr)
            vsh = max(0.0, min(1.0, self._vshale(igr)))
            results.append({**entry, "vshale": vsh})
        return results
