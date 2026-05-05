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
(``;``, ``--``, ``/*``, ``*/``) at process time as a baseline
defence; callers passing untrusted user input must still sanitise.

Algorithm:
    1. Validate ``by`` as a non-empty sequence of plain SQL identifiers.
    2. Validate ``aggs`` as a non-empty ``Mapping[str, str]`` whose keys
       are plain SQL identifiers and whose values are non-empty
       aggregation expression strings free of injection tokens.
    3. Build the DuckDB ``aggregate`` SELECT fragment:
       ``"region", SUM(amount) AS "total", ...``
    4. Build the group-by fragment: ``"region", "tier", ...``
    5. Call ``relation.aggregate(select_sql, group_fragment)`` and
       return the result wrapped in a new :class:`DuckdbDataBatch`.

    ```text
    group_fragment = '"col1", "col2", ...'
    select_sql     = '"col1", ..., SUM(x) AS "out1", ...'
    result         = relation.aggregate(select_sql, group_fragment)
    ```

References:
    [1] DuckDB Python API — DuckDBPyRelation.aggregate:
        https://duckdb.org/docs/api/python/relational_api
    [2] DuckDB SQL — GROUP BY aggregation syntax:
        https://duckdb.org/docs/sql/query_syntax/groupby
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class DuckdbAggregate(Knot):
    """Group rows by ``by`` and apply DuckDB aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: DuckdbDataBatch,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> DuckdbDataBatch:
        """Group the batch by the configured columns and apply DuckDB SQL aggregation expressions.

        Args:
            batch: The DuckdbDataBatch to group and aggregate.
            by: A sequence of column names to group on.
            aggs: A mapping of output column name to DuckDB aggregation expression.

        Returns:
            A new DuckdbDataBatch containing the aggregated result.
        """
        IdentifierValidator.validate_columns("DuckdbAggregate.by", by)
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "DuckdbAggregate: aggs must be a non-empty Mapping[output_name, expression]"
            )
        for output, expression in aggs.items():
            IdentifierValidator.validate_column(
                "DuckdbAggregate: output column", output
            )
            if not isinstance(expression, str) or not expression.strip():
                raise TypeError(
                    f"DuckdbAggregate: aggs[{output!r}] must be a non-empty SQL expression string"
                )
            self._reject_obvious_injection(expression)
        coerced_by: tuple[str, ...] = tuple(by)
        coerced_aggs: dict[str, str] = dict(aggs)
        quoted_by = [f'"{column}"' for column in coerced_by]
        group_fragment = ", ".join(quoted_by)
        select_fragments = list(quoted_by)
        for output, expression in coerced_aggs.items():
            select_fragments.append(f'{expression} AS "{output}"')
        select_sql = ", ".join(select_fragments)
        aggregated = batch.relation.aggregate(select_sql, group_fragment)
        return batch.with_relation(aggregated)

    @staticmethod
    def _reject_obvious_injection(expression: str) -> None:
        red_flags = (";", "--", "/*", "*/")
        for token in red_flags:
            if token in expression:
                raise ValueError(
                    f"DuckdbAggregate: aggregation expression contains "
                    f"forbidden token {token!r}; expressions must be a "
                    "single SQL aggregation with no comments or terminators"
                )
