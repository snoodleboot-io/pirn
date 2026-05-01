"""``DuckdbJoin`` — Tier-2 binary join via :meth:`duckdb.DuckDBPyRelation.join`.

This is the second-tier counterpart of :class:`PolarsJoin`. The caller
supplies either:

* ``on=``: a column name (or sequence of names) shared by both sides;
  the knot turns that into ``left.col = right.col [AND ...]`` predicates
  using DuckDB's ``USING (...)``-equivalent SQL, or
* ``condition=``: a raw SQL predicate string referencing both relations
  (e.g. ``"left.user_id = right.customer_id"``).

Supports the standard DuckDB join strategies: ``inner``, ``left``,
``right``, ``outer``, ``cross``.

SECURITY
--------
``on`` column names are validated as plain identifiers. ``condition``
strings are screened for the obvious injection tokens but are otherwise
passed straight through; sanitise user-derived input before passing.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DuckdbJoin(Knot):
    """Binary join over two :class:`DuckdbDataBatch` parents."""

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        on: str | Sequence[str] | None = None,
        condition: str | None = None,
        how: str = "inner",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed_how = ("inner", "left", "right", "outer", "cross")
        if how not in allowed_how:
            raise ValueError(
                f"DuckdbJoin: how must be one of {list(allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if on is not None or condition is not None:
                raise TypeError(
                    "DuckdbJoin: cross join takes no on= or condition="
                )
        else:
            if on is None and condition is None:
                raise TypeError(
                    "DuckdbJoin: provide on=<column(s)> for matching keys, "
                    "or condition=<sql> for an arbitrary predicate"
                )
            if on is not None and condition is not None:
                raise TypeError(
                    "DuckdbJoin: pass either on= or condition=, not both"
                )
        identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        coerced_on: tuple[str, ...] | None = None
        if on is not None:
            if isinstance(on, str):
                coerced_on = (on,)
            elif isinstance(on, Sequence) and not isinstance(on, bytes):
                coerced_on = tuple(on)
            else:
                raise TypeError(
                    "DuckdbJoin: on= must be a column name or a sequence of column names"
                )
            if not coerced_on:
                raise ValueError("DuckdbJoin: on= must be non-empty")
            for column in coerced_on:
                if not isinstance(column, str) or not column:
                    raise TypeError(
                        "DuckdbJoin: every column in on= must be a non-empty string"
                    )
                if not identifier_re.match(column):
                    raise ValueError(
                        f"DuckdbJoin: on= column {column!r} is not a plain identifier"
                    )
        if condition is not None:
            if not isinstance(condition, str) or not condition.strip():
                raise TypeError(
                    "DuckdbJoin: condition= must be a non-empty SQL string"
                )
            self._reject_obvious_injection(condition)
        self._on = coerced_on
        self._condition = condition
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: DuckdbDataBatch, right: DuckdbDataBatch, **_: Any
    ) -> DuckdbDataBatch:
        right_relation = self._align_right(left, right)
        # Materialise both sides as views on the shared connection. SQL
        # gives us deterministic JOIN syntax across DuckDB versions and
        # avoids ambiguity in unqualified column references.
        left_view = f"_pirn_join_left_{id(left.relation):x}"
        right_view = f"_pirn_join_right_{id(right_relation):x}"
        left.relation.create_view(left_view, replace=True)
        right_relation.create_view(right_view, replace=True)

        sql_how = self._how_to_sql(self._how)
        if self._how == "cross":
            sql = f"SELECT * FROM {left_view} CROSS JOIN {right_view}"
        elif self._on is not None:
            using_columns = ", ".join(f'"{column}"' for column in self._on)
            sql = (
                f"SELECT * FROM {left_view} {sql_how} JOIN {right_view} "
                f"USING ({using_columns})"
            )
        else:
            assert self._condition is not None
            sql = (
                f"SELECT * FROM {left_view} {sql_how} JOIN {right_view} "
                f"ON {self._condition}"
            )
        joined = left.connection.sql(sql)
        return left.with_relation(joined)

    @staticmethod
    def _how_to_sql(how: str) -> str:
        return {
            "inner": "INNER",
            "left": "LEFT",
            "right": "RIGHT",
            "outer": "FULL OUTER",
            "cross": "CROSS",
        }[how]

    def _align_right(
        self, left: DuckdbDataBatch, right: DuckdbDataBatch
    ) -> Any:
        """Ensure ``right.relation`` lives on ``left.connection``.

        DuckDB requires both sides of a relational join to come from
        the same in-process connection. When two upstream chains were
        built against independent connections, materialise the right
        side as Arrow and re-register it on the left's connection.
        """
        if right.connection is left.connection:
            return right.relation
        # ``arrow()`` returns a pyarrow Table from the relation and is
        # available across DuckDB Python versions.
        arrow_table = right.relation.arrow()
        view_name = f"_pirn_join_right_{id(arrow_table):x}"
        left.connection.register(view_name, arrow_table)
        return left.connection.table(view_name)

    def _reject_obvious_injection(self, value: str) -> None:
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in value:
                raise ValueError(
                    f"DuckdbJoin: condition contains forbidden token {token!r}"
                )
