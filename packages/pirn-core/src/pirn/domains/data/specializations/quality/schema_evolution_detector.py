"""``SchemaEvolutionDetector`` — diffs incoming schema against expected schema.

Queries the live table's column list from the database information schema
and compares it against the caller-supplied expected column set. Detects
added columns, dropped columns, and type-changed columns.

Algorithm:
    1. Receive resolved ``pool``, ``monitored_table``, ``expected_schema``,
       and ``schema_query`` in ``process()``.
    2. Validate all inputs: pool type, identifier safety, non-empty schema,
       non-empty query string.
    3. Execute ``schema_query`` to fetch ``(column_name, data_type)`` rows.
    4. Build normalised actual schema (lowercase names, uppercase types).
    5. Diff against normalised expected schema.
    6. Return result dict with ``added_columns``, ``dropped_columns``,
       ``type_changes``, and ``schema_changed``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class SchemaEvolutionDetector(Knot):
    """Diff a live table's schema against an expected column-to-type mapping."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        monitored_table: Knot | str,
        expected_schema: Knot | dict[str, str],
        schema_query: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            monitored_table=monitored_table,
            expected_schema=expected_schema,
            schema_query=schema_query,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        monitored_table: Any,
        expected_schema: Any,
        schema_query: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Query live schema and return added, dropped, and type-changed columns.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``added_columns``, ``dropped_columns``, ``type_changes``,
            and ``schema_changed``.

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When expected_schema is empty or schema_query is empty.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("SchemaEvolutionDetector: pool must be a DatabaseConnectionPool")
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        if not expected_schema:
            raise ValueError("SchemaEvolutionDetector: expected_schema must be non-empty")
        if not isinstance(schema_query, str) or not schema_query:
            raise ValueError("SchemaEvolutionDetector: schema_query must be a non-empty string")
        rows = await pool.fetch_all(schema_query)
        actual_schema: dict[str, str] = {str(row[0]).lower(): str(row[1]).upper() for row in rows}
        expected_normalised = {k.lower(): v.upper() for k, v in expected_schema.items()}
        added_columns = [col for col in actual_schema if col not in expected_normalised]
        dropped_columns = [col for col in expected_normalised if col not in actual_schema]
        type_changes = [
            {
                "column": col,
                "expected": expected_normalised[col],
                "actual": actual_schema[col],
            }
            for col in expected_normalised
            if col in actual_schema and actual_schema[col] != expected_normalised[col]
        ]
        schema_changed = bool(added_columns or dropped_columns or type_changes)
        return {
            "succeeded": True,
            "monitored_table": monitored_table,
            "added_columns": added_columns,
            "dropped_columns": dropped_columns,
            "type_changes": type_changes,
            "schema_changed": schema_changed,
        }
