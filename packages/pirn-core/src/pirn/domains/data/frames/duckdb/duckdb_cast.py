"""``DuckdbCast`` — Tier-2 type coercion via a DuckDB projection.

The ``casts`` mapping accepts column → DuckDB type-name string pairs
(e.g. ``{"id": "INTEGER", "amount": "DOUBLE", "label": "VARCHAR"}``).
Casts are emitted as ``CAST("col" AS TYPE) AS "col"`` projections;
columns not in the mapping are passed through unchanged.

Each type-name is validated against a tight allow-list pattern
(``^[A-Z][A-Z0-9_]*(\\([0-9, ]+\\))?$``) before being interpolated.
This rejects the obvious SQL-injection tokens (``;``, ``--``, ``'``,
quotes, comments) and anything that does not look like a DuckDB type
declaration. ``DECIMAL(p,s)`` and similar parametric types are
permitted.

Algorithm:
    1. Validate ``casts`` is a non-empty ``Mapping[str, str]``.
    2. For each ``(column, type_name)`` entry: reject forbidden
       identifier tokens in ``column``; normalise ``type_name`` to
       upper-case and reject it unless it matches
       ``^[A-Z][A-Z0-9_]*(\\([0-9, ]+\\))?$``.
    3. Filter ``casts`` to columns that actually exist in the upstream
       relation; if none apply, return the batch unchanged.
    4. For every column in the relation, emit either
       ``CAST("col" AS TYPE) AS "col"`` (if in casts) or
       ``"col"`` (pass-through).
    5. Call ``relation.project(fragment_list)`` and return the result.

    ```text
    applicable = {col: type for col, type in casts if col in relation.columns}
    fragments  = [CAST("col" AS TYPE) AS "col" if col in applicable else "col"
                  for col in relation.columns]
    return relation.project(", ".join(fragments))
    ```

References:
    [1] DuckDB SQL — CAST expression:
        https://duckdb.org/docs/sql/expressions/cast
    [2] DuckDB Python API — DuckDBPyRelation.project:
        https://duckdb.org/docs/api/python/relational_api
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class DuckdbCast(Knot):
    """Coerce per-column types via DuckDB ``CAST(... AS ...)`` projections."""

    def __init__(
        self,
        *,
        batch: Knot,
        casts: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, casts=casts, _config=_config, **kwargs)

    async def process(
        self,
        batch: DuckdbDataBatch,
        casts: Any,
        **_: Any,
    ) -> DuckdbDataBatch:
        """Cast the configured columns to their target DuckDB types and return the projected batch.

        Args:
            batch: The DuckdbDataBatch whose columns are to be cast.
            casts: A non-empty mapping of column name to DuckDB type-name string.

        Returns:
            A new DuckdbDataBatch with the configured columns cast to their target types.
        """
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError("DuckdbCast: casts must be a non-empty Mapping[column, type_name]")
        type_re = re.compile(r"^[A-Z][A-Z0-9_]*(\([0-9, ]+\))?$")
        for column, type_name in casts.items():
            if not isinstance(column, str) or not column:
                raise TypeError("DuckdbCast: casts keys must be non-empty strings")
            if not isinstance(type_name, str) or not type_name:
                raise TypeError(
                    f"DuckdbCast: casts[{column!r}] must be a non-empty DuckDB type-name string"
                )
            self._reject_unsafe_token("column", column)
            normalised = type_name.strip().upper()
            if not type_re.match(normalised):
                raise ValueError(
                    f"DuckdbCast: casts[{column!r}] = {type_name!r} does not look "
                    "like a DuckDB type name (expected e.g. INTEGER, DOUBLE, "
                    "VARCHAR, DECIMAL(10,2))"
                )
        coerced: dict[str, str] = {
            column: type_name.strip().upper() for column, type_name in casts.items()
        }
        applicable = {
            column: type_name
            for column, type_name in coerced.items()
            if column in batch.relation.columns
        }
        if not applicable:
            return batch
        fragments: list[str] = []
        for column in batch.relation.columns:
            IdentifierValidator.validate_column("DuckdbCast: upstream column", column)
            if column in applicable:
                fragments.append(f'CAST("{column}" AS {applicable[column]}) AS "{column}"')
            else:
                fragments.append(f'"{column}"')
        projected = batch.relation.project(", ".join(fragments))
        return batch.with_relation(projected)

    @staticmethod
    def _reject_unsafe_token(label: str, value: str) -> None:
        forbidden = ('"', "\\", ";", "--", "/*", "*/", "'")
        for token in forbidden:
            if token in value:
                raise ValueError(
                    f"DuckdbCast: {label} {value!r} contains forbidden token {token!r}"
                )
