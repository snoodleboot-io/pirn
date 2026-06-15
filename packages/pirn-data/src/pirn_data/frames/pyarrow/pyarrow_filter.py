"""``PyarrowFilter`` — Tier-2 row predicate using a native PyArrow expression
or a callable producing one.

Unlike Tier-1 :class:`pirn_data.transforms.filter.Filter` (which
takes a Python callable per row), this Knot expects either:

* ``expression``: a :class:`pyarrow.compute.Expression` (built with
  ``pyarrow.compute.field("col") == value`` etc.), or
* ``predicate``: a callable ``(table) -> pyarrow.Array[bool] |
  pyarrow.compute.Expression`` invoked against the upstream table at
  process time.

so the engine can apply the predicate vectorised across the table.

Algorithm:
    1. Validate that exactly one of ``expression`` or ``predicate`` is supplied.
    2. If ``expression``: apply it directly with ``table.filter(expression)``.
    3. If ``predicate``: invoke the callable to produce a mask or expression,
       then apply with ``table.filter(mask)``.
    4. Return the filtered table wrapped in a new :class:`PyarrowDataBatch`.

References:
    [1] PyArrow — Table.filter:
        https://arrow.apache.org/docs/python/generated/pyarrow.Table.html#pyarrow.Table.filter
    [2] PyArrow — compute.Expression:
        https://arrow.apache.org/docs/python/compute.html#expressions
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowFilter(Knot):
    """Apply a PyArrow predicate to a :class:`PyarrowDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        expression: Knot | Any | None = None,  # pc.Expression — pydantic-incompatible
        predicate: Knot | Callable[[pa.Table], Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            expression=expression,
            predicate=predicate,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: PyarrowDataBatch,
        expression: Any,  # pc.Expression | None — pydantic can't schema pc.Expression
        predicate: Any,  # Callable[[pa.Table], Any] | None — pydantic can't schema Callable
        **_: Any,
    ) -> PyarrowDataBatch:
        """Apply the configured expression or predicate to filter rows.

        Args:
            batch: The PyarrowDataBatch to filter.
            expression: A ``pyarrow.compute.Expression``, or None when using ``predicate``.
            predicate: A callable ``(table) -> mask | expression``, or None
                when using ``expression``.

        Returns:
            A new PyarrowDataBatch containing only rows that satisfy the filter.
        """
        if expression is None and predicate is None:
            raise TypeError(
                "PyarrowFilter: provide either expression=<pyarrow.compute.Expression> "
                "or predicate=<callable(table) -> pyarrow.Array[bool] | Expression>"
            )
        if expression is not None and predicate is not None:
            raise TypeError("PyarrowFilter: pass either expression= or predicate=, not both")
        if expression is not None:
            if not isinstance(expression, pc.Expression):  # type: ignore[attr-defined]
                raise TypeError(
                    "PyarrowFilter: expression must be a pyarrow.compute.Expression; "
                    "for row-by-row Python callables use the Tier-1 "
                    "pirn_data.transforms.filter.Filter knot instead"
                )
            return batch.with_table(batch.table.filter(expression))
        assert predicate is not None
        if not callable(predicate):
            raise TypeError(
                "PyarrowFilter: predicate must be callable(table) -> "
                "pyarrow.Array[bool] | pyarrow.compute.Expression"
            )
        return batch.with_table(batch.table.filter(predicate(batch.table)))
