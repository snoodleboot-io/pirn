"""``IbisSource`` — a pirn :class:`Source` that binds a Ibis connection +
table name and emits an :class:`IbisTable` expression.

The Source has no parents: it produces the deferred expression that
downstream tier-3 knots extend. The Ibis backend itself is the user's
responsibility — pirn accepts any object the Ibis ``connection.table()``
call works on, so any backend Ibis supports works (DuckDB, SQLite,
Snowflake, BigQuery, Postgres, MySQL, …).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.nodes.source import Source


class IbisSource(Source):
    """Bind an Ibis connection + table and emit a deferred expression."""

    def __init__(
        self,
        *,
        connection: Any,
        table: str,
        _config: KnotConfig,
        backend_name: str = "",
        source_uri: str = "",
        **kwargs: Any,
    ) -> None:
        if connection is None:
            raise TypeError("IbisSource: connection is required")
        if not isinstance(table, str) or not table:
            raise ValueError("IbisSource: table must be a non-empty string")
        self._connection = connection
        self._table = table
        self._backend_name = backend_name or self._derive_backend_name(connection)
        self._source_uri = source_uri
        super().__init__(_config=_config, **kwargs)

    @property
    def table(self) -> str:
        return self._table

    @property
    def backend_name(self) -> str:
        return self._backend_name

    async def process(self, **_: Any) -> IbisTable:
        """Bind the configured Ibis connection and table name into a deferred IbisTable expression.

        Returns:
            An IbisTable wrapping the deferred expression for the configured table.
        """
        expression = self._connection.table(self._table)
        return IbisTable(
            expression=expression,
            backend_name=self._backend_name,
            source_uri=self._source_uri,
        )

    @staticmethod
    def _derive_backend_name(connection: Any) -> str:
        """Best-effort backend label without requiring a particular Ibis API.

        Ibis exposes ``Backend.name`` on every backend; older versions used
        ``backend.name`` as a class attribute. Fall back to the class name.
        """
        for attr_path in (("name",), ("backend", "name")):
            target: Any = connection
            try:
                for part in attr_path:
                    target = getattr(target, part)
                if isinstance(target, str):
                    return target
            except AttributeError:
                continue
        return type(connection).__name__
