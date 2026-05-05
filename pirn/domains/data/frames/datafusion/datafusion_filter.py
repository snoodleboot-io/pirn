"""``DatafusionFilter`` — Tier-2 row predicate using either a SQL
predicate string or a callable producing a DataFusion expression.

DataFusion's :meth:`datafusion.DataFrame.filter` accepts both
:class:`datafusion.Expr` instances (built with ``df.col("x") > df.lit(1)``
etc.) and SQL string predicates that are parsed against the frame's
schema. This Knot supports both shapes:

* ``predicate``: a SQL fragment string (e.g. ``"region = 'EU' AND active"``).
* ``expression``: a callable ``(df.DataFrame) -> df.Expr`` invoked at
  process time so the caller can build expressions referring to the
  upstream frame's columns/aliases.

SECURITY
--------
The caller is responsible for sanitising any user-derived input before
it reaches the predicate string. :meth:`_reject_obvious_injection` catches
the most common red flags (statement terminators, line and block
comments) before the predicate hits the engine. Treat that check as
defence in depth, not a substitute for parameterised queries.

Algorithm:
    1. Validate that exactly one of ``predicate`` or ``expression`` is supplied.
    2. If ``predicate``: reject obvious SQL injection tokens, then call
       ``frame.filter(predicate)``.
    3. If ``expression``: invoke the callable against the upstream frame to
       produce a ``datafusion.Expr``, then call ``frame.filter(expr)``.
    4. Return the filtered frame wrapped in a new :class:`DatafusionDataBatch`.

References:
    [1] Apache DataFusion Python — DataFrame.filter:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.DataFrame.filter
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import datafusion as df

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class DatafusionFilter(Knot):
    """Apply a DataFusion predicate to a :class:`DatafusionDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Knot | str | None = None,
        expression: Knot | Callable[[df.DataFrame], df.Expr] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            predicate=predicate,
            expression=expression,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: DatafusionDataBatch,
        predicate: str | None,
        expression: Any,  # Callable[[df.DataFrame], df.Expr] | None — pydantic can't schema Callable
        **_: Any,
    ) -> DatafusionDataBatch:
        """Apply the configured SQL predicate or expression to filter rows.

        Args:
            batch: The DatafusionDataBatch to filter.
            predicate: A SQL fragment string, or None when using ``expression``.
            expression: A callable ``(frame) -> datafusion.Expr``, or None when
                using ``predicate``.

        Returns:
            A new DatafusionDataBatch containing only rows that satisfy the filter.
        """
        if predicate is None and expression is None:
            raise TypeError(
                "DatafusionFilter: provide either predicate=<sql string> "
                "or expression=<callable(frame) -> datafusion.Expr>"
            )
        if predicate is not None and expression is not None:
            raise TypeError(
                "DatafusionFilter: pass either predicate= or expression=, not both"
            )
        if predicate is not None:
            if not isinstance(predicate, str):
                raise TypeError("DatafusionFilter: predicate must be a SQL string")
            if not predicate.strip():
                raise ValueError(
                    "DatafusionFilter: predicate must not be empty or whitespace"
                )
            self._reject_obvious_injection(predicate)
            filtered = batch.frame.filter(predicate)
        else:
            assert expression is not None
            if not callable(expression):
                raise TypeError(
                    "DatafusionFilter: expression must be callable(frame) -> datafusion.Expr"
                )
            filtered = batch.frame.filter(expression(batch.frame))
        return batch.with_frame(filtered)

    @staticmethod
    def _reject_obvious_injection(predicate: str) -> None:
        # Line comments, block comments, and statement terminators have
        # no legitimate place in a single boolean expression. Flagging
        # them at process time blocks the most common injection patterns.
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in predicate:
                raise ValueError(
                    f"DatafusionFilter: predicate contains forbidden token "
                    f"{token!r}; predicates must be a single boolean "
                    "expression with no comments or statement terminators"
                )
