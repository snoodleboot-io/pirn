"""``SchemaEvolutionDetector`` — diffs incoming schema against expected schema.

Queries the live table's column list from the database information schema
and compares it against the caller-supplied expected column set. Detects
added columns, dropped columns, and type-changed columns.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class SchemaEvolutionDetector(SubTapestry):
    """Diff a live table's schema against an expected column-to-type mapping."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        monitored_table: str,
        expected_schema: dict[str, str],
        schema_query: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "SchemaEvolutionDetector: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        if not expected_schema:
            raise ValueError(
                "SchemaEvolutionDetector: expected_schema must be non-empty"
            )
        if not isinstance(schema_query, str) or not schema_query:
            raise ValueError(
                "SchemaEvolutionDetector: schema_query must be a non-empty string"
            )
        self._pool = pool
        self._monitored_table = monitored_table
        self._expected_schema = dict(expected_schema)
        self._schema_query = schema_query
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Query live schema and return added, dropped, and type-changed columns.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``added_columns``, ``dropped_columns``, ``type_changes``,
            and ``schema_changed``.
        """
        rows = await self._pool.fetch_all(self._schema_query)
        actual_schema: dict[str, str] = {
            str(row[0]).lower(): str(row[1]).upper() for row in rows
        }
        expected_normalised = {
            k.lower(): v.upper() for k, v in self._expected_schema.items()
        }
        added_columns = [
            col for col in actual_schema if col not in expected_normalised
        ]
        dropped_columns = [
            col for col in expected_normalised if col not in actual_schema
        ]
        type_changes = [
            {
                "column": col,
                "expected": expected_normalised[col],
                "actual": actual_schema[col],
            }
            for col in expected_normalised
            if col in actual_schema
            and actual_schema[col] != expected_normalised[col]
        ]
        schema_changed = bool(added_columns or dropped_columns or type_changes)
        return {
            "succeeded": True,
            "monitored_table": self._monitored_table,
            "added_columns": added_columns,
            "dropped_columns": dropped_columns,
            "type_changes": type_changes,
            "schema_changed": schema_changed,
        }
