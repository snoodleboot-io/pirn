"""``DuckdbFilter`` — Tier-2 row predicate using a DuckDB SQL fragment.

DuckDB's Python API does not (yet) expose a structured expression
builder analogous to ``polars.Expr``; predicates are passed as raw SQL
strings. This knot accepts a ``predicate`` SQL fragment (e.g.
``"region = 'EU' AND active"``) and feeds it directly to
:meth:`duckdb.DuckDBPyRelation.filter`.

SECURITY
--------
The caller is responsible for sanitising any user-derived input before
it reaches the predicate. We can't fully prevent SQL injection from a
freeform string, but :meth:`_reject_obvious_injection` catches the most
common red flags (statement terminators, line and block comments)
before the predicate hits the engine. Treat that check as defence in
depth, not a substitute for parameterised queries.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DuckdbFilter(Knot):
    """Apply a DuckDB SQL predicate to a :class:`DuckdbDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(predicate, str):
            raise TypeError(
                "DuckdbFilter: predicate must be a SQL string; "
                "DuckDB has no structured expression API like polars.Expr"
            )
        if not predicate.strip():
            raise ValueError("DuckdbFilter: predicate must not be empty or whitespace")
        self._reject_obvious_injection(predicate)
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> str:
        return self._predicate

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DuckdbDataBatch:
        return batch.with_relation(batch.relation.filter(self._predicate))

    def _reject_obvious_injection(self, predicate: str) -> None:
        # Line comments, block comments, and statement terminators have
        # no legitimate place in a single boolean expression. Flagging
        # them at construction time blocks the most common injection
        # patterns and the most common copy-paste mistakes.
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in predicate:
                raise ValueError(
                    f"DuckdbFilter: predicate contains forbidden token "
                    f"{token!r}; predicates must be a single boolean "
                    "expression with no comments or statement terminators"
                )
