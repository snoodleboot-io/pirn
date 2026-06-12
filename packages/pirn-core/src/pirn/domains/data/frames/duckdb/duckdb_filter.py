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

Algorithm:
    1. Validate that ``predicate`` is a non-empty string (not whitespace).
    2. Scan ``predicate`` for obvious injection tokens
       (``;``, ``--``, ``/*``, ``*/``); raise :class:`ValueError` if any
       are found.
    3. Call ``relation.filter(predicate)`` and return the result wrapped
       in a new :class:`DuckdbDataBatch`.

    ```text
    reject_injection(predicate)
    return batch.with_relation(batch.relation.filter(predicate))
    ```

References:
    [1] DuckDB Python API — DuckDBPyRelation.filter:
        https://duckdb.org/docs/api/python/relational_api
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
        predicate: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        batch: DuckdbDataBatch,
        predicate: Any,
        **_: Any,
    ) -> DuckdbDataBatch:
        """Apply the configured SQL predicate to filter rows and return the resulting batch.

        Args:
            batch: The DuckdbDataBatch to filter.
            predicate: A SQL fragment string used to filter rows.

        Returns:
            A new DuckdbDataBatch containing only the rows that satisfy the predicate.
        """
        if not isinstance(predicate, str):
            raise TypeError(
                "DuckdbFilter: predicate must be a SQL string; "
                "DuckDB has no structured expression API like polars.Expr"
            )
        if not predicate.strip():
            raise ValueError("DuckdbFilter: predicate must not be empty or whitespace")
        self._reject_obvious_injection(predicate)
        return batch.with_relation(batch.relation.filter(predicate))

    @staticmethod
    def _reject_obvious_injection(predicate: str) -> None:
        # Line comments, block comments, and statement terminators have
        # no legitimate place in a single boolean expression. Flagging
        # them at process time blocks the most common injection
        # patterns and the most common copy-paste mistakes.
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in predicate:
                raise ValueError(
                    f"DuckdbFilter: predicate contains forbidden token "
                    f"{token!r}; predicates must be a single boolean "
                    "expression with no comments or statement terminators"
                )
