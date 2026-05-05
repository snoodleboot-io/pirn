"""``BinningKnot`` — bucket a numeric column into bins.

Two strategies are supported:

* ``equal_width``  — bins of identical width between ``min`` and ``max``.
* ``quantile``     — bins with roughly equal population using sample
                     quantile cut-points.

The output column is named ``{source_column}_bin`` and contains the
1-based bin index (int).  Rows whose value falls outside the bin range
(only possible with ``equal_width`` at exact boundary edge cases) are
assigned to the nearest bin.

Algorithm:
    1. Receive resolved ``rows``, ``column``, ``num_bins``, and
       ``strategy`` in ``process()``.
    2. Validate ``column`` identifier, ``num_bins`` positivity, and
       ``strategy`` membership.
    3. Collect all numeric values from ``column`` across the input rows.
    4. Compute bin edges using the chosen strategy.
    5. Assign each row to a bin and append ``{column}_bin`` (1-based int).
    6. Return the enriched row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class BinningKnot(Knot):
    """Append a ``{column}_bin`` column with 1-based bin assignments."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        column: Knot | str,
        num_bins: Knot | int,
        strategy: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            column=column,
            num_bins=num_bins,
            strategy=strategy,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _equal_width_edges(vals: list[float], num_bins: int) -> list[float]:
        lo, hi = min(vals), max(vals)
        width = (hi - lo) / num_bins
        return [lo + i * width for i in range(num_bins + 1)]

    @staticmethod
    def _quantile_edges(vals: list[float], num_bins: int) -> list[float]:
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        edges = [sorted_vals[0]]
        for b in range(1, num_bins):
            idx = int(b * n / num_bins)
            edges.append(sorted_vals[min(idx, n - 1)])
        edges.append(sorted_vals[-1])
        return edges

    @staticmethod
    def _assign(value: float, edges: list[float], num_bins: int) -> int:
        for i in range(len(edges) - 1):
            lo = edges[i]
            hi = edges[i + 1]
            if i == len(edges) - 2:
                if lo <= value <= hi:
                    return i + 1
            else:
                if lo <= value < hi:
                    return i + 1
        return num_bins

    async def process(
        self,
        *,
        rows: Any,
        column: Any,
        num_bins: Any,
        strategy: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        IdentifierValidator.validate_column("column", column)
        if not isinstance(num_bins, int) or num_bins < 1:
            raise ValueError("BinningKnot: num_bins must be a positive integer")
        if strategy not in ("equal_width", "quantile"):
            raise ValueError("BinningKnot: strategy must be 'equal_width' or 'quantile'")
        output_column = f"{column}_bin"
        if not rows:
            return []
        vals = [float(r[column]) for r in rows]
        if strategy == "equal_width":
            edges = self._equal_width_edges(vals, num_bins)
        else:
            edges = self._quantile_edges(vals, num_bins)
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            new_row[output_column] = self._assign(float(row[column]), edges, num_bins)
            result.append(new_row)
        return result
