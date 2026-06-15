"""``IbisWindow`` — append window-function columns via Ibis ``mutate`` +
``ibis.window(...)``.

Same shape as :class:`pirn_data.frames.polars.polars_window_calc.PolarsWindowCalc`,
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

Algorithm:
    1. Validate that ``windows`` is callable.
    2. Invoke ``windows(expression)`` to produce one or more named window expressions.
    3. Call ``expression.mutate(*result)`` or ``expression.mutate(result)``
       depending on whether the factory returned a sequence.
    4. Return a new ``IbisTable`` wrapping the mutated deferred expression.

    The window clauses are not executed here — they are compiled into SQL
    ``OVER (...)`` clauses when the terminal sink materialises the expression.

    ```text
    result = windows(expression)
    if isinstance(result, (list, tuple)):
        mutated = expression.mutate(*result)
    else:
        mutated = expression.mutate(result)
    return IbisTable(mutated)
    ```

References:
    [1] Ibis — Table.mutate with window functions:
        https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.mutate
    [2] Ibis — Window functions overview:
        https://ibis-project.org/tutorial/analytics.html#window-functions
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ibis
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.ibis.ibis_table import IbisTable


class IbisWindow(Knot):
    """Append window-function columns via Ibis ``mutate``."""

    def __init__(
        self,
        *,
        batch: Knot,
        windows: Knot | Callable[[ibis.Table], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, windows=windows, _config=_config, **kwargs)

    async def process(self, batch: IbisTable, windows: Any, **_: Any) -> IbisTable:
        """Append the configured window-function columns to the deferred Ibis expression via mutate.

        Args:
            batch: The upstream IbisTable whose expression will be extended with window columns.
            windows: A callable (table) -> ibis.Expr or sequence of ibis.Expr.

        Returns:
            A new IbisTable with the window-function columns appended to the deferred expression.
        """
        if not callable(windows):
            raise TypeError(
                "IbisWindow: windows must be a callable (table) -> ibis.Expr "
                "or sequence of ibis.Expr"
            )
        result = windows(batch.expression)
        if isinstance(result, (list, tuple)):
            mutated = batch.expression.mutate(*result)  # type: ignore[arg-type]
        else:
            mutated = batch.expression.mutate(result)  # type: ignore[arg-type]
        return batch.with_expression(mutated)
