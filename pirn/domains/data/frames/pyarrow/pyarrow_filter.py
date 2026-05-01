"""``PyarrowFilter`` — Tier-2 row predicate using a native PyArrow expression
or a callable producing one.

Unlike Tier-1 :class:`pirn.domains.data.transforms.filter.Filter` (which
takes a Python callable per row), this knot expects either:

* ``expression``: a :class:`pyarrow.compute.Expression` (built with
  ``pyarrow.compute.field("col") == value`` etc.), or
* ``predicate``: a callable ``(table) -> pyarrow.Array[bool] |
  pyarrow.compute.Expression`` invoked against the upstream table at
  process time.

so the engine can apply the predicate vectorised across the table.
"""

from __future__ import annotations

from typing import Any, Callable

import pyarrow as pa
import pyarrow.compute as pc

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowFilter(Knot):
    """Apply a PyArrow predicate to a :class:`PyarrowDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        expression: pc.Expression | None = None,
        predicate: Callable[[pa.Table], Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if expression is None and predicate is None:
            raise TypeError(
                "PyarrowFilter: provide either expression=<pyarrow.compute.Expression> "
                "or predicate=<callable(table) -> pyarrow.Array[bool] | Expression>"
            )
        if expression is not None and predicate is not None:
            raise TypeError(
                "PyarrowFilter: pass either expression= or predicate=, not both"
            )
        if expression is not None and not isinstance(expression, pc.Expression):
            raise TypeError(
                "PyarrowFilter: expression must be a pyarrow.compute.Expression; "
                "for row-by-row Python callables use the Tier-1 "
                "pirn.domains.data.transforms.filter.Filter knot instead"
            )
        if predicate is not None and not callable(predicate):
            raise TypeError(
                "PyarrowFilter: predicate must be callable(table) -> "
                "pyarrow.Array[bool] | pyarrow.compute.Expression"
            )
        self._expression = expression
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def expression(self) -> pc.Expression | None:
        return self._expression

    async def process(self, batch: PyarrowDataBatch, **_: Any) -> PyarrowDataBatch:
        if self._expression is not None:
            mask: Any = self._expression
        else:
            assert self._predicate is not None
            mask = self._predicate(batch.table)
        return batch.with_table(batch.table.filter(mask))
