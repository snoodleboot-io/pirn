"""``DuckdbAggregate`` — Tier-2 group-by + aggregation via DuckDB's
relation API.

The caller passes:

* ``by``: tuple of column names to group on (each must be a plain SQL
  identifier),
* ``aggs``: mapping of *output column name* → DuckDB aggregation
  expression string (e.g. ``"SUM(amount)"``).

These are stitched into a call to
:meth:`duckdb.DuckDBPyRelation.aggregate`, which takes a single SQL
fragment representing the SELECT list. Output column names go through
the same identifier check as the group-by columns.

SECURITY
--------
Aggregation expressions are not parsed by us — they are interpolated
into the SQL fragment. We reject the obvious injection tokens
(``;``, ``--``, ``/*``, ``*/``) at construction time as a baseline
defence; callers passing untrusted user input must still sanitise.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DuckdbAggregate(Knot):
    """Group rows by ``by`` and apply DuckDB aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Sequence[str],
        aggs: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError(
                "DuckdbAggregate: by must be a sequence of column names"
            )
        if not by:
            raise ValueError("DuckdbAggregate: by must be non-empty")
        identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for column in by:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    "DuckdbAggregate: every entry in by must be a non-empty string"
                )
            if not identifier_re.match(column):
                raise ValueError(
                    f"DuckdbAggregate: by entry {column!r} is not a plain identifier"
                )
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "DuckdbAggregate: aggs must be a non-empty Mapping[output_name, expression]"
            )
        for output, expression in aggs.items():
            if not isinstance(output, str) or not output:
                raise TypeError(
                    "DuckdbAggregate: aggs keys must be non-empty strings"
                )
            if not identifier_re.match(output):
                raise ValueError(
                    f"DuckdbAggregate: output column {output!r} is not a plain identifier"
                )
            if not isinstance(expression, str) or not expression.strip():
                raise TypeError(
                    f"DuckdbAggregate: aggs[{output!r}] must be a non-empty SQL expression string"
                )
            self._reject_obvious_injection(expression)
        self._by: tuple[str, ...] = tuple(by)
        self._aggs: dict[str, str] = dict(aggs)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    @property
    def aggs(self) -> Mapping[str, str]:
        return dict(self._aggs)

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DuckdbDataBatch:
        quoted_by = [f'"{column}"' for column in self._by]
        group_fragment = ", ".join(quoted_by)
        select_fragments = list(quoted_by)
        for output, expression in self._aggs.items():
            select_fragments.append(f'{expression} AS "{output}"')
        select_sql = ", ".join(select_fragments)
        aggregated = batch.relation.aggregate(select_sql, group_fragment)
        return batch.with_relation(aggregated)

    def _reject_obvious_injection(self, expression: str) -> None:
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in expression:
                raise ValueError(
                    f"DuckdbAggregate: aggregation expression contains "
                    f"forbidden token {token!r}; expressions must be a "
                    "single SQL aggregation with no comments or terminators"
                )
