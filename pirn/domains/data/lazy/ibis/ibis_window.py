"""``IbisWindow`` — append window-function columns via Ibis ``mutate`` +
``ibis.window(...)``.

Same shape as :class:`pirn.domains.data.frames.polars.polars_window_calc.PolarsWindowCalc`,
but at Tier 3: every window function travels through the deferred
expression and gets compiled into the final SQL window clauses
(``ROW_NUMBER() OVER (...)``, ``LAG(...)``, ``RANK()``, …) when the
sink executes.

The factory receives the upstream ``ibis.Table`` and returns either a
single named expression or a sequence of them::

    IbisWindow(
        batch=upstream,
        windows=lambda t: [
            t.amount.rank().over(group_by=t.region).name("rank_in_region"),
            t.amount.cumsum().over(order_by=t.id).name("running_total"),
        ],
        _config=KnotConfig(id="windowed"),
    )
"""

from __future__ import annotations

from typing import Any, Callable

import ibis

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


class IbisWindow(Knot):
    """Append window-function columns via Ibis ``mutate``."""

    def __init__(
        self,
        *,
        batch: Knot,
        windows: Callable[[ibis.Table], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(windows):
            raise TypeError(
                "IbisWindow: windows must be a callable (table) -> ibis.Expr "
                "or sequence of ibis.Expr"
            )
        self._windows = windows
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: IbisTable, **_: Any) -> IbisTable:
        """Append the configured window-function columns to the deferred Ibis expression via mutate.

        Args:
            batch: The upstream IbisTable whose expression will be extended with window columns.

        Returns:
            A new IbisTable with the window-function columns appended to the deferred expression.
        """
        result = self._windows(batch.expression)
        if isinstance(result, (list, tuple)):
            mutated = batch.expression.mutate(*result)
        else:
            mutated = batch.expression.mutate(result)
        return batch.with_expression(mutated)
