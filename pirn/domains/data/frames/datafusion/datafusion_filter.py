"""``DatafusionFilter`` — Tier-2 row predicate using either a SQL
predicate string or a callable producing a DataFusion expression.

DataFusion's :meth:`datafusion.DataFrame.filter` accepts both
:class:`datafusion.Expr` instances (built with ``df.col("x") > df.lit(1)``
etc.) and SQL string predicates that are parsed against the frame's
schema. This knot supports both shapes:

* ``predicate``: a SQL fragment string (e.g. ``"region = 'EU' AND active"``).
* ``expression``: a callable ``(df.DataFrame) -> df.Expr`` invoked at
  process time so the caller can build expressions referring to the
  upstream frame's columns/aliases.

SECURITY
--------
The caller is responsible for sanitising any user-derived input before
it reaches the predicate string. We can't fully prevent SQL injection
from a freeform string, but :meth:`_reject_obvious_injection` catches
the most common red flags (statement terminators, line and block
comments) before the predicate hits the engine. Treat that check as
defence in depth, not a substitute for parameterised queries.
"""

from __future__ import annotations

from typing import Any, Callable

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
        predicate: str | None = None,
        expression: Callable[[df.DataFrame], df.Expr] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
                raise TypeError(
                    "DatafusionFilter: predicate must be a SQL string"
                )
            if not predicate.strip():
                raise ValueError(
                    "DatafusionFilter: predicate must not be empty or whitespace"
                )
            self._reject_obvious_injection(predicate)
        if expression is not None and not callable(expression):
            raise TypeError(
                "DatafusionFilter: expression must be callable(frame) -> datafusion.Expr"
            )
        self._predicate = predicate
        self._expression = expression
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> str | None:
        return self._predicate

    async def process(
        self, batch: DatafusionDataBatch, **_: Any
    ) -> DatafusionDataBatch:
        if self._predicate is not None:
            filtered = batch.frame.filter(self._predicate)
        else:
            assert self._expression is not None
            filtered = batch.frame.filter(self._expression(batch.frame))
        return batch.with_frame(filtered)

    def _reject_obvious_injection(self, predicate: str) -> None:
        # Line comments, block comments, and statement terminators have
        # no legitimate place in a single boolean expression. Flagging
        # them at construction time blocks the most common injection
        # patterns and the most common copy-paste mistakes.
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in predicate:
                raise ValueError(
                    f"DatafusionFilter: predicate contains forbidden token "
                    f"{token!r}; predicates must be a single boolean "
                    "expression with no comments or statement terminators"
                )
