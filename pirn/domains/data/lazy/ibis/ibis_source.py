"""``IbisSource`` — a pirn :class:`Source` that binds an Ibis connection and
a table name, emitting an :class:`IbisTable` expression.

The Source has no parents: it produces the deferred expression that
downstream tier-3 Knots extend. The Ibis backend is supplied via an
:class:`IbisConnectionKnot` upstream, which wraps any Ibis backend that
supports the ``connection.table(name)`` contract (DuckDB, SQLite, Snowflake,
BigQuery, Postgres, MySQL, …).

Algorithm:
    1. Receive the resolved :class:`IbisConnection` wrapper and a table name
       string from upstream Knots.
    2. Validate that ``table`` is a non-empty string.
    3. Unwrap the Ibis backend via ``connection.backend``.
    4. Call ``backend.table(table)`` to obtain a deferred Ibis expression.
    5. Derive the backend label via :meth:`_derive_backend_name` if
       ``backend_name`` is not supplied.
    6. Wrap the expression in :class:`IbisTable` and return it.

References:
    [1] Ibis Project — backends and connections:
        https://ibis-project.org/backends/
    [2] Ibis — Table expression API:
        https://ibis-project.org/reference/expression-tables
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection
from pirn.domains.data.lazy.ibis.ibis_connection_knot import IbisConnectionKnot
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.nodes.source import Source


class IbisSource(Source):
    """Bind an Ibis connection + table and emit a deferred expression."""

    def __init__(
        self,
        *,
        connection: IbisConnectionKnot,
        table: Knot | str,
        _config: KnotConfig,
        backend_name: Knot | str = "",
        source_uri: Knot | str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            connection=connection,
            table=table,
            backend_name=backend_name,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        connection: IbisConnection,
        table: str,
        backend_name: str = "",
        source_uri: str = "",
        **_: Any,
    ) -> IbisTable:
        """Bind the Ibis connection and table name into a deferred IbisTable expression.

        Args:
            connection: Resolved :class:`IbisConnection` wrapping the Ibis backend.
            table: Name of the table to bind.
            backend_name: Optional label for the backend; derived automatically
                if not supplied.
            source_uri: Optional URI for lineage tracking.

        Returns:
            An :class:`IbisTable` wrapping the deferred expression.

        Raises:
            ValueError: If ``table`` is empty or not a string.
        """
        if not isinstance(table, str) or not table:
            raise ValueError("IbisSource: table must be a non-empty string")
        from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection

        backend = connection.backend if isinstance(connection, IbisConnection) else connection
        resolved_backend_name = backend_name or self._derive_backend_name(backend)
        expression = backend.table(table)
        return IbisTable(
            expression=expression,
            backend_name=resolved_backend_name,
            source_uri=source_uri,
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
