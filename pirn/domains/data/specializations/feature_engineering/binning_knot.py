"""``BinningKnot`` — bucket a numeric column into bins.

Two strategies are supported:

* ``equal_width``  — bins of identical width between ``min`` and ``max``.
* ``quantile``     — bins with roughly equal population using sample
                     quantile cut-points.

The output column is named ``{source_column}_bin`` and contains the
1-based bin index (int).  Rows whose value falls outside the bin range
(only possible with ``equal_width`` at exact boundary edge cases) are
assigned to the nearest bin.
"""

from __future__ import annotations

from typing import Any, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class BinningKnot(Knot):
    """Append a ``{column}_bin`` column with 1-based bin assignments."""

    def __init__(
        self,
        *,
        rows: Knot,
        column: str,
        num_bins: int,
        strategy: Literal["equal_width", "quantile"] = "equal_width",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("column", column)
        if not isinstance(num_bins, int) or num_bins < 1:
            raise ValueError(
                "BinningKnot: num_bins must be a positive integer"
            )
        if strategy not in ("equal_width", "quantile"):
            raise ValueError(
                "BinningKnot: strategy must be 'equal_width' or 'quantile'"
            )
        self._column = column
        self._num_bins = num_bins
        self._strategy = strategy
        self._output_column = f"{column}_bin"
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _equal_width_edges(self, vals: list[float]) -> list[float]:
        lo, hi = min(vals), max(vals)
        width = (hi - lo) / self._num_bins
        return [lo + i * width for i in range(self._num_bins + 1)]

    def _quantile_edges(self, vals: list[float]) -> list[float]:
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        edges = [sorted_vals[0]]
        for b in range(1, self._num_bins):
            idx = int(b * n / self._num_bins)
            edges.append(sorted_vals[min(idx, n - 1)])
        edges.append(sorted_vals[-1])
        return edges

    def _assign(self, value: float, edges: list[float]) -> int:
        for i in range(len(edges) - 1):
            lo = edges[i]
            hi = edges[i + 1]
            if i == len(edges) - 2:
                if lo <= value <= hi:
                    return i + 1
            else:
                if lo <= value < hi:
                    return i + 1
        return self._num_bins

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Compute bin edges from all values then assign each row to a bin.

        Args:
            rows: Upstream rows with a numeric ``column``.

        Returns:
            Rows with ``{column}_bin`` (1-based int) appended.
        """
        if not rows:
            return []
        vals = [float(r[self._column]) for r in rows]
        if self._strategy == "equal_width":
            edges = self._equal_width_edges(vals)
        else:
            edges = self._quantile_edges(vals)
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            new_row[self._output_column] = self._assign(
                float(row[self._column]), edges
            )
            result.append(new_row)
        return result
